from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

from src import config

def _get_sqlite_connection() -> sqlite3.Connection:
    db_path: Path = config.SQLITE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            company TEXT NOT NULL,
            cumulative_value REAL NOT NULL,
            delta_kwh REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn

def _fetch_last_reading(conn: sqlite3.Connection, company: str) -> Optional[Tuple[str, float, float]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT timestamp, cumulative_value, delta_kwh FROM readings WHERE company = ? ORDER BY id DESC LIMIT 1",
        (company,),
    )
    row = cur.fetchone()
    return row if row is not None else None

def store_reading(company: str, raw_values: list[float], timestamp: Optional[dt.datetime] = None) -> Tuple[float, float]:
    timestamp = timestamp or dt.datetime.now(dt.timezone.utc)
    cumulative_value = float(sum(v for v in raw_values if v is not None))
    conn = _get_sqlite_connection()
    try:
        last = _fetch_last_reading(conn, company)
        if last is not None:
            last_value = last[1]
            cumulative_value = cumulative_value / 1000.0
            delta = cumulative_value - last_value
        else:
            delta = 0.0
        delta_kwh = delta
        conn.execute(
             "INSERT INTO readings (timestamp,company, cumulative_value, delta_kwh) VALUES(?, ?, ?, ?)",
            (timestamp.isoformat(), company, cumulative_value, delta_kwh),
        )
        conn.commit()
        return cumulative_value, delta_kwh
    finally:
        conn.close()
