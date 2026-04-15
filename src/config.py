from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_local_env() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()


@dataclass(frozen=True)
class CompanyConfig:
    key: str
    name: str
    mode: str
    host: str
    port: int
    unit_id: int
    registers: list[int]


COMPANIES: dict[str, CompanyConfig] = {
    "EMPRESA1": CompanyConfig(
        key="EMPRESA1",
        name="EMPRESA1",
        mode="rtu_over_tcp",
        host="10.111.00.11",
        port=1001,
        unit_id=1,
        registers=[111],
    ),
    "EMPRESA2": CompanyConfig(
        key="EMPRESA2",
        name="EMPRESA2",
        mode="rtu_over_tcp",
        host="10.111.00.11",
        port=1001,
        unit_id=1,
        registers=[000],
    ),
}

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_PATH: Path = Path(os.environ.get("ENERGY_DB_PATH", str(DATA_DIR / "consumption.db")))
CONTACTS_FILE: Path = Path(os.environ.get("ENERGY_CONTACTS_FILE", str(DATA_DIR / "contacts.json")))

REPORT_DAY: int = int(os.environ.get("ENERGY_REPORT_DAY", "20"))
REPORTS_DIR: Path = Path(os.environ.get("ENERGY_REPORTS_DIR", str(BASE_DIR / "reports")))

SMTP_HOST: str = os.environ.get("SMTP_HOST", "mail.com.br")
SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "25"))
SMTP_USE_TLS: bool = os.environ.get("SMTP_USE_TLS", "false")
SMTP_USERNAME: str = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM: str = os.environ.get("EMAIL_FROM", SMTP_USERNAME)
SMTP_TIMEOUT_SECONDS: float = float(os.environ.get("SMTP_TIMEOUT_SECONDS", "15"))

MODBUS_TIMEOUT_SECONDS: float = float(os.environ.get("MODBUS_TIMEOUT_SECONDS", "8"))

CONTACTS_ACCESS_PASSWORD: str = os.environ.get("CONTACTS_ACCESS_PASSWORD", "")


def load_contacts() -> dict[str, dict[str, Any]]:
    if not CONTACTS_FILE.exists():
        return {}
    try:
        with CONTACTS_FILE.open("r", encoding="utf-8") as contacts_file:
            data = json.load(contacts_file)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    contacts: dict[str, dict[str, Any]] = {}
    for name, info in data.items():
        if isinstance(name, str) and isinstance(info, dict):
            contacts[name] = info
    return contacts


def save_contacts(contacts: dict[str, dict[str, Any]]) -> None:
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONTACTS_FILE.open("w", encoding="utf-8") as contacts_file:
        json.dump(contacts, contacts_file, ensure_ascii=False, indent=2)
