import asyncio
import struct
import logging
import argparse

from src.core.bus import InMemoryBus
from src.core.models import Tag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("PollingEngine")

DEFAULT_TAG_MAP = {
    0: "Boiler_Temp_01",
    1: "System_Pressure_01",
    2: "Pump_01_Status",
    3: "Alarm_Code_01",
    4: "Temp_Setpoint_01",
}


class ModbusResponseError(ValueError):
    """The controller returned an invalid FC03 response."""


class PollingEngine:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5020,
        interval: float = 1.0,
        bus: InMemoryBus | None = None,
        tag_map: dict[int, str] | None = None,
        timeout: float = 3.0,
        retry_interval: float = 3.0,
    ):
        self.host = host
        self.port = port
        self.interval = interval
        self.bus = bus if bus is not None else InMemoryBus()
        self.tag_map = tag_map if tag_map is not None else DEFAULT_TAG_MAP
        if timeout <= 0 or retry_interval < 0:
            raise ValueError("timeout must be positive and retry_interval non-negative")
        if not self.tag_map or any(not isinstance(address, int) or not 0 <= address < 125 for address in self.tag_map):
            raise ValueError("tag_map must contain register addresses between 0 and 124")
        self.timeout = timeout
        self.retry_interval = retry_interval
        self._running = False
        self.transaction_id = 1

        # Инициализируем теги в шине со статусом BAD (до первого успешного опроса)
        for tag_id in self.tag_map.values():
            if self.bus.get(tag_id) is None:
                self.bus.publish(Tag(id=tag_id, value=0.0, quality="BAD"))

    def _mark_all_tags_bad(self):
        """
        Помечает все опрашиваемые теги как недостоверные (BAD) при потере связи (требование FR-01.1).

        Гарантирует, что при разрыве TCP-соединения или сбое контроллера оператор не увидит
        устаревшие значения под видом актуальных технологических данных.
        """
        for tag_id in self.tag_map.values():
            tag = self.bus.get(tag_id)
            if tag:
                tag.set_bad_quality()
                self.bus.publish(tag)
        logger.warning("All tags set to quality: BAD due to communication failure (FR-01.1).")

    async def _read_registers(self, writer: asyncio.StreamWriter, reader: asyncio.StreamReader):
        """
        Формирует запрос (FC 03), отправляет его и читает ответ.
        """
        register_count = max(max(self.tag_map) + 1, 5)
        request = struct.pack(">HHHBBHH", self.transaction_id, 0, 6, 1, 3, 0, register_count)
        writer.write(request)
        # One deadline covers both the write and the complete response.
        async with asyncio.timeout(self.timeout):
            await writer.drain()
            header = await reader.readexactly(7)
            tx_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            if tx_id != self.transaction_id or protocol_id != 0 or unit_id != 1:
                raise ModbusResponseError("Invalid Modbus transaction, protocol or unit ID")
            if not 3 <= length <= 253:
                raise ModbusResponseError("Invalid Modbus response length")
            pdu = await reader.readexactly(length - 1)

        if pdu[0] != 3:
            raise ModbusResponseError(f"Unexpected Modbus function 0x{pdu[0]:02x}")
        expected_bytes = register_count * 2
        if length != expected_bytes + 3 or pdu[1] != expected_bytes or len(pdu) != expected_bytes + 2:
            raise ModbusResponseError("Invalid FC03 register count or payload length")
        values = struct.unpack(f">{register_count}H", pdu[2:])
        for address, tag_id in self.tag_map.items():
            tag = self.bus.get(tag_id) or Tag(id=tag_id)
            tag.update_value(values[address])
            self.bus.publish(tag)
        return values

    def stop(self):
        """Остановка цикла опроса."""
        self._running = False

    async def run(self):
        self._running = True
        logger.info("Starting Polling Engine targeting %s:%s", self.host, self.port)
        while self._running:
            writer = None
            failed = False
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
                logger.info("Connected to PLC at %s:%s", self.host, self.port)
                while self._running:
                    await self._read_registers(writer, reader)
                    self.transaction_id = (self.transaction_id + 1) % 65536
                    await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                failed = True
                logger.exception("PLC polling failed; retrying in %s seconds", self.retry_interval)
                self._mark_all_tags_bad()
            finally:
                if writer is not None:
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), self.timeout)
                    except (OSError, asyncio.TimeoutError):
                        logger.debug("Error closing PLC connection", exc_info=True)
            if failed and self._running:
                await asyncio.sleep(self.retry_interval)
        logger.info("Polling Engine stopped.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Mini-SCADA Polling Engine"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="PLC host",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5020,
        help="PLC Modbus TCP port",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds",
    )

    args = parser.parse_args()

    print("Mini-SCADA Polling Engine")
    print("Version: 0.1.0")
    print(f"Connecting to: {args.host}:{args.port}")

    engine = PollingEngine(
        host=args.host,
        port=args.port,
        interval=args.interval,
    )

    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        logger.info("Polling Engine stopped by user.")