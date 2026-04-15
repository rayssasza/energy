from __future__ import annotations

import logging
from typing import Callable, List

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from src import config

logger = logging.getLogger(__name__)

def _create_client_for_company(company_key: str) -> tuple[ModbusTcpClient, Callable[[], None]]:
    company = config.COMPANIES[company_key]
    client = ModbusTcpClient(company.host, port=company.port)
    return client, client.close

def _read_register_with_compat(client: ModbusTcpClient, address: int, unit_id: int):
    try:
        return client.read_holding_registers(address, count=2, slave=unit_id)
    except TypeError:
        return client.read_holding_registers(address, count=2, unit=unit_id)

def read_registers(registers: list[int], company_key: str = "EMPRESA1") -> List[float | None]:
    if company_key not in config.COMPANIES:
        raise KeyError(f"Empresa inválida: {company_key}. Válidas: {list(config.COMPANIES.keys())}")

    company = config.COMPANIES[company_key]
    client, close_client = _create_client_for_company(company_key)

    try:
        if not client.connect():
            raise ConnectionError(f"Não conectou ao Modbus em {company.host}:{company.port} ({company.name})")

        values: List[float | None] = []
        for addr in registers:
            try:
                rr = _read_register_with_compat(client, addr, company.unit_id)
                if rr.isError():
                    logger.warning("Erro Modbus (%s) addr=%s: %s", company.name, addr, rr)
                    values.append(None)
                else:
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        rr.registers,
                        byteorder=Endian.BIG,
                        wordorder=Endian.LITTLE
                    )
                    valor_real = round(decoder.decode_32bit_float(), 2)
                    values.append(valor_real)
            except ModbusIOException as exc:
                logger.warning("IOException Modbus (%s) addr=%s: %s", company.name, addr, exc)
                values.append(None)

        return values
    finally:
        close_client()

def read_company(company_key: str) -> List[float | None]:
    if company_key not in config.COMPANIES:
        raise KeyError(f"Empresa inválida: {company_key}. Válidas: {list(config.COMPANIES.keys())}")
    return read_registers(config.COMPANIES[company_key].registers, company_key=company_key)
