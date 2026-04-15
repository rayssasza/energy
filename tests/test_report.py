import datetime as dt
from pathlib import Path

import pytest

try:
    from src import report, data_processing, config  # type: ignore
except ModuleNotFoundError:
    pytest.skip("Required reporting dependencies not installed; skipping report tests", allow_module_level=True)


def test_generate_and_send_report(monkeypatch, tmp_path):
    db_file = tmp_path / "db.sqlite"
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(config, "SQLITE_PATH", db_file)
    monkeypatch.setattr(config, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(config, "load_contacts", lambda: {})
    email_calls = {}

    def fake_send_email(to_address: str, subject: str, body: str, attachment_path: Path) -> None:
        email_calls['args'] = (to_address, subject, body, attachment_path)

    monkeypatch.setattr(report, "_send_email", fake_send_email)
    month_start = dt.datetime(2026, 1, 1, 0, 0)
    data_processing.store_reading('EMPRESA1', [0], timestamp=month_start)
    data_processing.store_reading('EMPRESA1', [100], timestamp=month_start + dt.timedelta(minutes=15))
    data_processing.store_reading('EMPRESA2', [0], timestamp=month_start)
    data_processing.store_reading('EMPRESA2', [300], timestamp=month_start + dt.timedelta(minutes=15))
    reference_date = dt.datetime(2026, 2, 15, 12, 0)
    pdf_path, totals = report.generate_and_send_report(reference_date=reference_date)
    assert pdf_path.exists()
    assert pytest.approx(totals['EMPRESA1'], rel=1e-6) == 0.1
    assert pytest.approx(totals['EMPRESA2'], rel=1e-6) == 0.3
    assert email_calls == {}
