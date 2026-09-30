import struct
import pytest

from src.core.models import Tag
from src.core.bus import InMemoryBus


def test_modbus_mbap_header_packing():
    """Проверка правильности формирования заголовка MBAP (7 байт, Big-Endian)."""
    transaction_id = 42
    protocol_id = 0
    length = 6
    unit_id = 1

    header = struct.pack('>HHHB', transaction_id, protocol_id, length, unit_id)
    assert len(header) == 7

    unpacked_tx, unpacked_proto, unpacked_len, unpacked_unit = struct.unpack('>HHHB', header)
    assert unpacked_tx == 42
    assert unpacked_proto == 0
    assert unpacked_len == 6
    assert unpacked_unit == 1


def test_modbus_fc03_request_packing():
    """Проверка сборки полного пакета запроса на чтение регистров (FC 03)."""
    tx_id = 1
    length = 6
    unit_id = 1
    fc = 3
    start_addr = 0
    reg_count = 5

    request = struct.pack('>HHHBBHH', tx_id, 0, length, unit_id, fc, start_addr, reg_count)
    assert len(request) == 12

    # Проверяем распаковку
    tx, proto, ln, uid, function_code, addr, count = struct.unpack('>HHHBBHH', request)
    assert function_code == 3
    assert addr == 0
    assert count == 5


def test_modbus_fc03_response_parsing():
    """Проверка разбора полезной нагрузки ответа FC 03 (значения регистров)."""
    # Имитируем ответ ПЛК: 5 регистров (10 байт): 750 (75.0 C), 210 (2.10 bar), 1, 0, 800
    mock_registers = (750, 210, 1, 0, 800)
    byte_count = len(mock_registers) * 2

    pdu_header = struct.pack('BB', 3, byte_count)
    pdu_data = struct.pack(f'>{len(mock_registers)}H', *mock_registers)
    full_pdu = pdu_header + pdu_data

    # Парсим обратно
    resp_fc = full_pdu[0]
    resp_byte_cnt = full_pdu[1]
    parsed_registers = struct.unpack(f'>{resp_byte_cnt // 2}H', full_pdu[2:])

    assert resp_fc == 3
    assert resp_byte_cnt == 10
    assert parsed_registers == (750, 210, 1, 0, 800)


def test_tag_quality_on_nan():
    """Проверка отсечения битых данных (NaN/None) в Tag."""
    tag = Tag(id="TEST_TAG", value=10.0, quality="GOOD")
    tag.update_value(float("nan"))
    assert tag.quality == "BAD"

    tag.update_value(None)
    assert tag.quality == "BAD"

    tag.update_value(25.5)
    assert tag.quality == "GOOD"
    assert tag.value == 25.5
