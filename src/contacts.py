from __future__ import annotations

from typing import Any

from src import config


def load_contacts() -> dict[str, dict[str, Any]]:
    return config.load_contacts()


def save_contacts(contacts: dict[str, dict[str, Any]]) -> None:
    config.save_contacts(contacts)
