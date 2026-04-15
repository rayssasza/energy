from __future__ import annotations

import datetime as dt
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src import data_processing
from src import modbus_client
from src import report

MANUAL_COLLECT_RESULTS_KEY = "manual_collect_results"


def _read_data_from_path(db_path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(
            "SELECT timestamp, company, cumulative_value, delta_kwh FROM readings",
            conn,
        )
    except Exception as exc:
        if "no such table" in str(exc).lower():
            return pd.DataFrame()
        raise
    finally:
        conn.close()


def _prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prepared = df.copy()
    prepared["company"] = prepared["company"].astype(str).str.strip().str.upper()
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_convert("America/Sao_Paulo")
    prepared["cumulative_value"] = pd.to_numeric(prepared["cumulative_value"], errors="coerce")
    prepared["delta_kwh"] = pd.to_numeric(prepared["delta_kwh"], errors="coerce")
    prepared = prepared.dropna(subset=["timestamp", "company", "cumulative_value", "delta_kwh"])
    return prepared.sort_values("timestamp") if not prepared.empty else prepared


def _split_known_unknown_companies(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df
    configured = set(config.COMPANIES.keys())
    known = df[df["company"].isin(configured)].copy()
    unknown = df[~df["company"].isin(configured)].copy()
    return known, unknown


def _latest_by_company(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.groupby("company", as_index=False)["timestamp"].max().sort_values("company")


def _load_snapshot() -> pd.DataFrame:
    db_path = Path(config.SQLITE_PATH)

    if not db_path.exists():
        st.error(f"Banco de dados não encontrado no caminho oficial: `{db_path}`")
        return pd.DataFrame()

    return _prepare_data(_read_data_from_path(db_path))


def _plot_consumption(prepared: pd.DataFrame) -> None:
    known, _ = _split_known_unknown_companies(prepared)

    if prepared.empty:
        st.info("Nenhum dado disponível. Aguarde a próxima coleta.")
        return

    if known.empty:
        st.info("Ainda não há leituras para as empresas configuradas (EMPRESA1/EMPRESA2).")
        return

    st.subheader("Últimas leituras registradas")
    st.dataframe(
        known[["timestamp", "company", "cumulative_value", "delta_kwh"]]
        .sort_values("timestamp", ascending=False)
        .head(20),
        width="stretch",
    )

    configured_companies = list(config.COMPANIES.keys())

    latest_points = known.sort_values("timestamp").groupby("company", as_index=False).tail(1)
    metric_cols = st.columns(len(configured_companies))
    for idx, company in enumerate(configured_companies):
        row = latest_points[latest_points["company"] == company]
        if row.empty:
            metric_cols[idx].metric(company, "sem leitura")
        else:
            metric_cols[idx].metric(company, f"{float(row.iloc[0]['cumulative_value']):.1f}")

    st.caption("Consumo acumulado por empresa")
    cumulative = (
        known.pivot_table(index="timestamp", columns="company", values="cumulative_value", aggfunc="last")
        .sort_index()
        .reindex(columns=configured_companies)
    )
    st.line_chart(cumulative)

    st.caption("Consumo diário (delta kWh) por empresa")
    daily = known.assign(date=known["timestamp"].dt.date).groupby(["date", "company"], as_index=False)["delta_kwh"].sum()
    daily_pivot = daily.pivot(index="date", columns="company", values="delta_kwh").fillna(0)
    daily_pivot = daily_pivot.reindex(columns=configured_companies, fill_value=0)
    st.bar_chart(daily_pivot)


def _show_status(prepared: pd.DataFrame) -> None:
    known, _ = _split_known_unknown_companies(prepared)

    if prepared.empty:
        st.warning("Nenhuma leitura registrada ainda.")
        return

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    latest = _latest_by_company(known)

    if known.empty:
        st.warning("Não há leituras de EMPRESA1/EMPRESA2 no banco selecionado.")
        return

    st.subheader("Status por empresa")
    stale_companies: list[str] = []

    for _, row in latest.iterrows():
        company = str(row["company"])
        last_time = row["timestamp"]
        delta = now - last_time.to_pydatetime()
        minutes = int(delta.total_seconds() / 60)
        if delta.total_seconds() < 900:
            st.success(f"{company}: última leitura em {last_time} (há {minutes} minutos)")
        else:
            stale_companies.append(company)
            st.error(f"{company}: última leitura em {last_time} (há {minutes} minutos)")

    known_companies = set(latest["company"].astype(str).tolist()) if not latest.empty else set()
    missing_companies = [company for company in config.COMPANIES if company not in known_companies]
    for company in missing_companies:
        stale_companies.append(company)
        st.error(f"{company}: sem leitura registrada no banco ainda.")

    if stale_companies:
        st.warning("Empresas com leitura atrasada/ausente: " + ", ".join(sorted(set(stale_companies))))
    else:
        st.success("Todas as empresas estão atualizando dentro da janela esperada (15 minutos).")

    st.caption("Últimos registros gravados")
    st.dataframe(
        known[["timestamp", "company", "cumulative_value", "delta_kwh"]]
        .sort_values("timestamp", ascending=False)
        .head(10),
        width="stretch",
    )


def _collect_now_from_dashboard() -> list[str]:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    results: list[str] = []

    for company_key in config.COMPANIES:
        try:
            raw_values = modbus_client.read_company(company_key)
            cumulative, delta = data_processing.store_reading(company_key, raw_values, timestamp=now)
            results.append(f"✅ {company_key}: cumulative={cumulative}, delta_kwh={delta}")
        except Exception as exc:
            results.append(f"❌ {company_key}: erro na coleta ({exc})")

    return results


def _show_manual_collect_feedback() -> None:
    results = st.session_state.pop(MANUAL_COLLECT_RESULTS_KEY, None)
    if not results:
        return
    st.write("Resultado da coleta manual:")
    for line in results:
        st.write(line)


def _send_test_report() -> None:
    contacts = config.load_contacts()
    emails = [info.get("email") for info in contacts.values() if info.get("email")]
    if not emails:
        st.warning("Nenhum contato com e-mail cadastrado para enviar relatório de teste.")
        return

    try:
        report_file, totals = report.generate_and_send_report(dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))))
    except Exception as exc:
        st.error(f"Falha ao enviar relatório de teste: {exc}")
        return

    st.success(f"Relatório de teste enviado para {len(emails)} contato(s)")
    st.write(f"Totais do relatório: EMPRESA1={totals.get('EMPRESA1', 0.0):.2f} kWh | EMPRESA2={totals.get('EMPRESA2', 0.0):.2f} kWh")

def _manage_contacts():
    import time
    import streamlit as st
    from src import config

    st.subheader("Gerenciar Contatos")
    contacts = config.load_contacts()

    contact_names = ["Novo contato"] + list(contacts.keys())
    selected = st.selectbox("Selecione um contato ou crie um novo", contact_names)

    if selected == "Novo contato":
        new_name = st.text_input("Nome do contato")
        new_email = st.text_input("E-mail")
    else:
        new_name = selected
        new_email = st.text_input("E-mail", value=contacts[selected].get("email", ""))

    st.markdown("---")
    action_password = st.text_input("Senha do Sistema", type="password", key="action_pass")

    btn_salvar = False
    btn_excluir = False

    if selected == "Novo contato":
        btn_salvar = st.button("Salvar Contato", use_container_width=True)
    else:
        col1, col2 = st.columns(2)
        with col1:
            btn_salvar = st.button("Salvar Contato", use_container_width=True)
        with col2:
            btn_excluir = st.button("Excluir Contato", type="primary", use_container_width=True)

    if btn_salvar:
        if action_password != config.CONTACTS_ACCESS_PASSWORD:
            st.error("Senha inválida.")
        else:
            contacts[new_name] = {"email": new_email}
            if selected != "Novo contato" and selected != new_name:
                del contacts[selected]
            config.save_contacts(contacts)
            st.success("Contato salvo com sucesso!")
            time.sleep(1.5)
            st.rerun()

    if btn_excluir:
        if action_password != config.CONTACTS_ACCESS_PASSWORD:
            st.error("Senha inválida.")
        else:
            del contacts[selected]
            config.save_contacts(contacts)
            st.success("Contato excluído!")
            time.sleep(1.5)
            st.rerun()

def main() -> None:
    st.set_page_config(page_title="Monitoramento de Energia", layout="wide")
    st.title("Sistema de Monitoramento de Energia")

    prepared = _load_snapshot()

    tab1, tab2, tab3 = st.tabs(["Visão Geral", "Status", "Contatos"])
    with tab1:
        st.subheader("Consumo Diário (kWh)")
        _plot_consumption(prepared)
    with tab2:
        st.subheader("Status da Conexão")
        _show_manual_collect_feedback()

        if st.button("Coletar agora"):
            with st.spinner("Coletando dados das empresas..."):
                st.session_state[MANUAL_COLLECT_RESULTS_KEY] = _collect_now_from_dashboard()
            st.rerun()

        if st.button("Enviar relatório de teste por e-mail"):
            with st.spinner("Gerando e enviando relatório de teste..."):
                _send_test_report()

        _show_status(prepared)
    with tab3:
        _manage_contacts()


if __name__ == "__main__":
    main()
