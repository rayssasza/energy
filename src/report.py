from __future__ import annotations

import datetime as dt
import smtplib
import sqlite3
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Tuple

from fpdf import FPDF, XPos, YPos

from src import config

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

def _fetch_monthly_totals(month_start: dt.datetime, month_end: dt.datetime) -> Dict[str, float]:
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=15.0)
    try:
        cur = conn.cursor()
        totals: Dict[str, float] = {}
        for company in ("EMPRESA1", "EMPRESA2"):
            cur.execute(
                """
                SELECT SUM(delta_kwh) FROM readings
                WHERE company = ? AND timestamp >= ? AND timestamp <= ?
                """,
                (company, month_start.isoformat(), month_end.isoformat()),
            )
            row = cur.fetchone()
            totals[company] = row[0] if row[0] is not None else 0.0
        return totals
    finally:
        conn.close()

def _create_pdf_report(period_label: str, totals: Dict[str, float], file_path: Path) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16, style="B")
    pdf.cell(0, 10, f"Relatório de Consumo - {period_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "Este relatório apresenta o consumo de energia das empresas EMPRESA1 e EMPRESA2 durante o período informado. "
        "Todos os valores são calculados a partir de leituras obtidas a cada 15 minutos.\n\n",
    )
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.cell(40, 8, "Empresa", border=1)
    pdf.cell(60, 8, "Consumo total (kWh)", border=1)
    pdf.ln()
    pdf.set_font("Helvetica", size=12)
    for company, value in totals.items():
        pdf.cell(40, 8, f"{company}", border=1)
        pdf.cell(60, 8, f"{value:.2f}", border=1)
        pdf.ln()
    pdf.ln(10)
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        0,
        6,
        "Relatório gerado automaticamente pelo sistema de monitoramento de energia. "
        "Para dúvidas ou correções, entre em contato com o setor responsável da elétrica.",
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(file_path))

def _send_email(to_address: str, subject: str, body: str, attachment_path: Path) -> None:
    msg = EmailMessage()
    msg["From"] = config.EMAIL_FROM
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)
    with attachment_path.open("rb") as file_obj:
        pdf_data = file_obj.read()
    msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=attachment_path.name)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT_SECONDS) as server:
        server.send_message(msg)

def generate_and_send_report(reference_date: dt.datetime | None = None) -> Tuple[Path, Dict[str, float]]:
    brt_tz = dt.timezone(dt.timedelta(hours=-3))
    reference_date = reference_date or dt.datetime.now(brt_tz)

    curr_month_start = dt.datetime(reference_date.year, reference_date.month, 1, tzinfo=brt_tz)
    curr_month_end = reference_date

    prev_month_end = curr_month_start - dt.timedelta(microseconds=1)
    prev_month_start = dt.datetime(prev_month_end.year, prev_month_end.month, 1, tzinfo=brt_tz)

    totals = _fetch_monthly_totals(prev_month_start, prev_month_end)

    if totals["EMPRESA1"] == 0.0 and totals["EMPRESA2"] == 0.0:
        totals = _fetch_monthly_totals(curr_month_start, curr_month_end)
        active_start = curr_month_start
    else:
        active_start = prev_month_start

    nome_mes = MESES_PT[active_start.month]
    period_label = f"{nome_mes} de {active_start.year}"

    report_file = config.REPORTS_DIR / f"relatorio_{active_start.strftime('%Y_%m')}.pdf"
    _create_pdf_report(period_label, totals, report_file)

    body = (
        f"Olá,\n\nSegue em anexo o relatório de consumo de energia referente a {period_label}.\n"
        f"A EMPRESA1 consumiu {totals['EMPRESA1']:.2f} kWh e a EMPRESA2 consumiu {totals['EMPRESA2']:.2f} kWh durante o período.\n\n"
        "Atenciosamente,\nEquipe da Elétrica EMPRESA1"
    )
    subject = f"Relatório de Consumo – {period_label}"

    contacts = config.load_contacts()
    for _, info in contacts.items():
        email = info.get("email")
        if email:
            _send_email(email, subject, body, report_file)

    return report_file, totals
