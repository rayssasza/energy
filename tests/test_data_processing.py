import datetime as dt
from pathlib import Path

import pytest

from src import data_processing, config


def test_store_reading_computes_delta(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(config, "SQLITE_PATH", db_file)
    cumulative, delta = data_processing.store_reading('EMPRESA1', [100, 0])
    assert cumulative == 100.0
    assert delta == 0.0 
    cumulative2, delta2 = data_processing.store_reading('EMPRESA1', [150, None])
    assert cumulative2 == 150.0
    assert pytest.approx(delta2, rel=1e-6) == 0.05
    cumulative_EMPRESA2, delta_EMPRESA2 = data_processing.store_reading('EMPRESA2', [200])
    assert cumulative_EMPRESA2 == 200.0
    assert delta_EMPRESA2 == 0.0
