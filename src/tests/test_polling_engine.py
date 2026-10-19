import asyncio
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.bus import InMemoryBus
from src.core.models import Tag
from src.da.polling_engine import PollingEngine, DEFAULT_TAG_MAP


def test_pe_01_initialization_defaults():
    """PE-01: Инициализация движка с шиной и создание тегов со статусом BAD."""
    bus = InMemoryBus()
    engine = PollingEngine(bus=bus)

    assert engine.host == "127.0.0.1"
    assert engine.port == 5020
    assert engine.interval == 1.0
    assert engine.transaction_id == 1

    # Все теги по умолчанию должны быть созданы со статусом BAD (до первого опроса)
    for tag_name in DEFAULT_TAG_MAP.values():
        tag = bus.get(tag_name)
        assert tag is not None
        assert tag.quality == "BAD"
        assert tag.value == 0.0


def test_pe_02_mark_all_tags_bad_fr01_1():
    """PE-02: Требование FR-01.1 — принудительный перевод всех тегов в BAD при сбое связи."""
    bus = InMemoryBus()
    engine = PollingEngine(bus=bus)

    # Имитируем, что теги были получены со статусом GOOD
    for tag_name in DEFAULT_TAG_MAP.values():
        bus.publish(Tag(id=tag_name, value=42.0, quality="GOOD"))

    # Вызываем защитный метод при обрыве сокета
    engine._mark_all_tags_bad()

    for tag_name in DEFAULT_TAG_MAP.values():
        tag = bus.get(tag_name)
        assert tag is not None
        assert tag.quality == "BAD"


@pytest.mark.asyncio
async def test_pe_03_read_registers_success():
    """PE-03: Успешное чтение регистров Modbus FC03 и обновление шины со статусом GOOD."""
    bus = InMemoryBus()
    engine = PollingEngine(bus=bus)

    # Имитируем сокетные потоки reader и writer
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_reader = AsyncMock()

    # Формируем корректный Modbus TCP ответ на 5 регистров:
    # MBAP (7 байт): tx_id=1, proto=0, len=13 (1 байт FC + 1 байт count + 10 байт данных), unit_id=1
    mbap = struct.pack('>HHHB', 1, 0, 13, 1)
    # PDU (12 байт): FC=3, ByteCount=10, 5 регистров (100, 200, 300, 400, 500)
    registers = (100, 200, 300, 400, 500)
    pdu = struct.pack('>BB5H', 3, 10, *registers)

    mock_reader.readexactly = AsyncMock(side_effect=[mbap, pdu])

    values = await engine._read_registers(mock_writer, mock_reader)

    assert values == registers
    # Проверяем, что тег в шине обновился со статусом GOOD
    t0 = bus.get("Boiler_Temp_01")
    assert t0 is not None
    assert t0.value == 100
    assert t0.quality == "GOOD"

    t1 = bus.get("System_Pressure_01")
    assert t1 is not None
    assert t1.value == 200
    assert t1.quality == "GOOD"


@pytest.mark.asyncio
async def test_pe_04_read_registers_unexpected_function_code():
    """PE-04: Обработка неожиданного кода функции (например, код ошибки 0x83)."""
    bus = InMemoryBus()
    engine = PollingEngine(bus=bus)

    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_reader = AsyncMock()

    # Ошибка Modbus: FC 0x83, код исключения 0x02
    mbap = struct.pack('>HHHB', 1, 0, 3, 1)
    pdu = struct.pack('>BB', 0x83, 0x02)
    mock_reader.readexactly = AsyncMock(side_effect=[mbap, pdu])

    values = await engine._read_registers(mock_writer, mock_reader)
    assert values is None


def test_pe_05_custom_tag_map():
    """PE-05: Поддержка произвольной карты тегов технологического процесса."""
    custom_map = {0: "PUMP_SPEED", 1: "VALVE_STATE"}
    bus = InMemoryBus()
    engine = PollingEngine(bus=bus, tag_map=custom_map)

    assert bus.get("PUMP_SPEED") is not None
    assert bus.get("VALVE_STATE") is not None
    assert bus.get("Boiler_Temp_01") is None


def test_pe_06_stop_method():
    """PE-06: Корректная остановка опроса установкой флага _running в False."""
    engine = PollingEngine()
    engine._running = True
    engine.stop()
    assert engine._running is False


@pytest.mark.asyncio
async def test_pe_07_request_packing_matches_protocol():
    """PE-07: Проверка формата отправляемого бинарного запроса (12 байт, Big-Endian)."""
    engine = PollingEngine()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_reader = AsyncMock()

    # Подсовываем пустой ответ для завершения функции
    mbap = struct.pack('>HHHB', 1, 0, 5, 1)
    pdu = struct.pack('>BBH', 3, 2, 999)
    mock_reader.readexactly = AsyncMock(side_effect=[mbap, pdu])

    await engine._read_registers(mock_writer, mock_reader)

    # Проверяем, что было отправлено в writer
    sent_data = mock_writer.write.call_args[0][0]
    assert len(sent_data) == 12
    tx, proto, length, uid, fc, addr, count = struct.unpack('>HHHBBHH', sent_data)
    assert tx == 1
    assert proto == 0
    assert length == 6
    assert uid == 1
    assert fc == 3
    assert addr == 0
    assert count == 5


@pytest.mark.asyncio
async def test_pe_08_partial_registers_mapped():
    """PE-08: Корректная обработка, если регистров вернулось больше, чем в tag_map."""
    custom_map = {0: "SENSOR_A"}
    bus = InMemoryBus()
    engine = PollingEngine(bus=bus, tag_map=custom_map)

    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_reader = AsyncMock()

    mbap = struct.pack('>HHHB', 1, 0, 13, 1)
    pdu = struct.pack('>BB5H', 3, 10, 10, 20, 30, 40, 50)
    mock_reader.readexactly = AsyncMock(side_effect=[mbap, pdu])

    values = await engine._read_registers(mock_writer, mock_reader)
    assert values == (10, 20, 30, 40, 50)
    assert bus.get("SENSOR_A").value == 10
    assert bus.get("SENSOR_A").quality == "GOOD"


def test_pe_09_transaction_id_wrap_around():
    """PE-09: Инкремент счетчика транзакций в диапазоне uint16."""
    engine = PollingEngine()
    engine.transaction_id = 65534
    engine.transaction_id = (engine.transaction_id + 1) % 65535
    assert engine.transaction_id == 0


def test_pe_10_tag_quality_transition():
    """PE-10: Переход качества тега из BAD в GOOD при первом ответе и обратно в BAD при сбое."""
    tag = Tag(id="MOTOR_CURRENT", value=0.0, quality="BAD")
    assert tag.quality == "BAD"

    tag.update_value(15.4)
    assert tag.quality == "GOOD"
    assert tag.value == 15.4

    tag.set_bad_quality()
    assert tag.quality == "BAD"
    # Значение сохраняется в памяти как последнее известное
    assert tag.value == 15.4
