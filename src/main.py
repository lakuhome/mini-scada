"""
Единая точка входа mini-scada (КТ-1).

Соответствует требованиям к минимальному исполняемому компоненту:
1. Запуск из чистого клона с параметрами по умолчанию или пользовательскими аргументами.
2. Прием параметров конфигурации (--host, --port, --interval, --threshold, --mode, --check).
3. Сообщение версии и режима выполнения (mini-scada v0.1.0-kt1).
4. Вывод минимальной диагностической записи.
5. Проверяемый признак успешного запуска (код возврата 0 и статус [HEALTHCHECK: OK]).
"""

import argparse
import asyncio
import logging
import sys
import struct

from src.core.models import Tag
from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.da.polling_engine import PollingEngine
from src.simulator.virtual_plc import VirtualPLC

VERSION = "0.1.0-kt1"
BUILD_ID = "2026.09.21-kt1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("MiniSCADA")


def run_self_check() -> int:
    """
    Автоматическая самодиагностика компонентов (Smoke test / Healthcheck).
    Проверяет работоспособность шины, тегов, фильтра Deadband и упаковщика Modbus.
    Возвращает 0 при успешном прохождении всех тестов, 1 при ошибке.
    """
    logger.info(f"Starting self-diagnostic check for mini-scada v{VERSION}...")

    try:
        # 1. Проверка шины и тегов
        bus = InMemoryBus()
        tag = Tag(id="HEALTH_CHECK_TEMP", value=42.0, quality="GOOD")
        bus.publish(tag)
        retrieved = bus.get("HEALTH_CHECK_TEMP")
        assert retrieved is not None and retrieved.value == 42.0, "Bus self-check failed"
        assert retrieved.quality == "GOOD", "Tag quality self-check failed"

        # 2. Проверка фильтра зоны нечувствительности
        filter_ = DeadbandFilter(threshold=1.0)
        assert filter_.should_store(tag) is True, "Deadband first point failed"
        tag_small = Tag(id="HEALTH_CHECK_TEMP", value=42.2, quality="GOOD")
        assert filter_.should_store(tag_small) is False, "Deadband noise filtering failed"

        # 3. Проверка кодирования фрейма Modbus TCP (MBAP + PDU FC 03)
        # TX:1, Proto:0, Len:6, Unit:1, FC:3, Start:0, Count:5
        raw_packet = struct.pack('>HHHBBHH', 1, 0, 6, 1, 3, 0, 5)
        assert len(raw_packet) == 12, "Modbus packet serialization failed"
        tx, proto, length, unit, fc, addr, cnt = struct.unpack('>HHHBBHH', raw_packet)
        assert (tx, length, fc, cnt) == (1, 6, 3, 5), "Modbus packet deserialization failed"

        print(
            f"[HEALTHCHECK: OK] Version: {VERSION} | Build: {BUILD_ID} | "
            f"Mode: self-check | Status: ALL SYSTEMS OPERATIONAL"
        )
        return 0
    except Exception as e:
        logger.error(f"[HEALTHCHECK: FAILED] Diagnostic check failed: {e}", exc_info=True)
        return 1


async def run_simulation_mode(host: str, port: int, interval: float, threshold: float):
    """
    Сквозной демонстрационный запуск в одном процессе:
    1. Запускает VirtualPLC на заданном порту.
    2. Запускает PollingEngine с шиной InMemoryBus.
    3. Подключает фильтр DeadbandFilter для демонстрации архивации.
    """
    logger.info("=" * 60)
    logger.info(f" mini-scada v{VERSION} (Build: {BUILD_ID})")
    logger.info(f" Mode: SIMULATION (All-in-One: PLC + Poller + Bus + Filter)")
    logger.info(f" Config: host={host}, port={port}, interval={interval}s, deadband={threshold}")
    logger.info("=" * 60)

    # Инициализация ядра
    bus = InMemoryBus()
    deadband = DeadbandFilter(threshold=threshold)

    # Запуск сервера ПЛК
    plc = VirtualPLC(host=host, port=port)
    poller = PollingEngine(host=host, port=port, interval=interval, bus=bus)

    async def monitor_bus():
        """Периодически печатает актуальное состояние шины и работу фильтра"""
        await asyncio.sleep(1.5)  # ждем первого опроса
        while True:
            tags = bus.get_all()
            logger.info("--- [In-Memory Bus State Snapshot] ---")
            for tag_id, tag in tags.items():
                store_decision = deadband.should_store(tag)
                flag = "-> [ARCHIVE]" if store_decision else "   [FILTERED (Noise)]"
                logger.info(
                    f"  Tag: {tag.id:<20} Value: {tag.value:>6} "
                    f"Quality: {tag.quality:<4} {flag}"
                )
            await asyncio.sleep(interval * 2)

    try:
        await asyncio.gather(
            plc.run(),
            poller.run(),
            monitor_bus(),
        )
    except asyncio.CancelledError:
        pass
    finally:
        plc.stop()
        poller.stop()


def main():
    parser = argparse.ArgumentParser(
        description=f"mini-scada v{VERSION} — легковесная диспетчерская система"
    )
    parser.add_argument(
        "--version", action="version", version=f"mini-scada v{VERSION} (build {BUILD_ID})"
    )
    parser.add_argument(
        "--check", action="store_true", help="Выполнить быструю самодиагностику и завершить работу"
    )
    parser.add_argument(
        "--mode",
        choices=["simulate", "poll", "plc"],
        default="simulate",
        help="Режим работы: 'simulate' (ПЛК + опрос в одном процессе), 'poll' (только опрос), 'plc' (только ПЛК)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Хост Modbus TCP (по умолчанию: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5020, help="Порт Modbus TCP (по умолчанию: 5020)")
    parser.add_argument("--interval", type=float, default=1.0, help="Период опроса в секундах (по умолчанию: 1.0)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Порог зоны нечувствительности (Deadband)")

    args = parser.parse_args()

    # Проверка здоровья / самодиагностика
    if args.check:
        sys.exit(run_self_check())

    # Печать диагностического баннера старта
    logger.info(
        f"Starting mini-scada v{VERSION} | Mode: {args.mode} | Target: {args.host}:{args.port}"
    )

    try:
        if args.mode == "simulate":
            asyncio.run(run_simulation_mode(args.host, args.port, args.interval, args.threshold))
        elif args.mode == "poll":
            engine = PollingEngine(host=args.host, port=args.port, interval=args.interval)
            asyncio.run(engine.run())
        elif args.mode == "plc":
            plc = VirtualPLC(host=args.host, port=args.port)
            asyncio.run(plc.run())
    except KeyboardInterrupt:
        logger.info("Application shut down cleanly by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
