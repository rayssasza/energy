from typing import List

import sys
import types

import pytest


def _ensure_pymodbus_dummy():
    if 'pymodbus' in sys.modules:
        return
    client_mod = types.SimpleNamespace(
        ModbusTcpClient=object,
        ModbusSerialClient=object,
    )
    exc_mod = types.SimpleNamespace(ModbusIOException=Exception)
    pymodbus_mod = types.SimpleNamespace(client=client_mod, exceptions=exc_mod)
    sys.modules['pymodbus'] = pymodbus_mod
    sys.modules['pymodbus.client'] = client_mod
    sys.modules['pymodbus.exceptions'] = exc_mod


_ensure_pymodbus_dummy()
from src import modbus_client


class DummyModbusResponse:
    def __init__(self, value: int) -> None:
        self.registers = [value]

    def isError(self) -> bool:
        return False


class DummyClient:
    def connect(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def read_holding_registers(self, address: int, count: int = 1, unit: int = 1) -> DummyModbusResponse:
        return DummyModbusResponse(address * 2)


def test_read_registers_returns_values(monkeypatch):
    dummy = DummyClient()

    def fake_create_client() -> tuple[DummyClient, callable]:
        return dummy, lambda: None

    monkeypatch.setattr(modbus_client, "_create_client", fake_create_client)
    registers = [1, 2, 3]
    values: List[int] = modbus_client.read_registers(registers)
    assert values == [2, 4, 6]


def test_read_registers_fallback_unit_kwarg(monkeypatch):
    class OldClient(DummyClient):
        def read_holding_registers(self, address: int, count: int = 1, unit: int = 1):
            return super().read_holding_registers(address, count=count, unit=unit)

    old_client = OldClient()

    def compat_read_holding_registers(address: int, count: int = 1, slave: int = 1):
        raise TypeError("unexpected keyword argument 'slave'")

    old_client.read_holding_registers = compat_read_holding_registers

    def fallback_read_holding_registers(address: int, count: int = 1, unit: int = 1):
        return DummyModbusResponse(address + unit)

    calls = {"called": False}

    def wrapped(address: int, count: int = 1, **kwargs):
        if "slave" in kwargs:
            return compat_read_holding_registers(address, count=count, slave=kwargs["slave"])
        calls["called"] = True
        return fallback_read_holding_registers(address, count=count, unit=kwargs["unit"])

    old_client.read_holding_registers = wrapped

    monkeypatch.setattr(modbus_client, "_create_client", lambda: (old_client, lambda: None))
    values = modbus_client.read_registers([10])
    assert values == [11]
    assert calls["called"] is True
