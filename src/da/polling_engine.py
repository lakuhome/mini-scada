import asyncio
import struct
import logging

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


class PollingEngine:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5020,
        interval: float = 1.0,
        bus: InMemoryBus | None = None,
        tag_map: dict[int, str] | None = None,
    ):
        self.host = host
        self.port = port
        self.interval = interval
        self.bus = bus if bus is not None else InMemoryBus()
        self.tag_map = tag_map if tag_map is not None else DEFAULT_TAG_MAP
        self._running = False
        self.transaction_id = 1

        # Инициализируем теги в шине со статусом BAD (до первого успешного опроса)
        for tag_id in self.tag_map.values():
            if self.bus.get(tag_id) is None:
                self.bus.publish(Tag(id=tag_id, value=0.0, quality="BAD"))

    def _mark_all_tags_bad(self):
        """Помечает все опрашиваемые теги как недостоверные (BAD) при потере связи."""
        for tag_id in self.tag_map.values():
            tag = self.bus.get(tag_id)
            if tag:
                tag.set_bad_quality()
                self.bus.publish(tag)
        logger.warning("All tags set to quality: BAD due to communication failure.")

    async def _read_registers(self, writer: asyncio.StreamWriter, reader: asyncio.StreamReader):
        """
        Формирует запрос (FC 03), отправляет его и читает ответ.
        """
        start_address = 0
        register_count = max(len(self.tag_map), 5)
        
        length = 6
        unit_id = 1
        function_code = 3
        
        request_bytes = struct.pack(
            '>HHHBBHH', 
            self.transaction_id, 0, length, unit_id, 
            function_code, start_address, register_count
        )
        
        writer.write(request_bytes)
        await writer.drain()
        logger.debug(f"Sent request TX: {self.transaction_id} for {register_count} registers.")

        mbap_bytes = await reader.readexactly(7)
        tx_id, proto_id, resp_len, resp_unit_id = struct.unpack('>HHHB', mbap_bytes)

        pdu_bytes = await reader.readexactly(resp_len - 1)
        resp_fc = pdu_bytes[0]
        byte_count = pdu_bytes[1]
        
        if resp_fc == 3:
            values_count = byte_count // 2
            data_format = f'>{values_count}H'
            
            values = struct.unpack(data_format, pdu_bytes[2:])
            logger.info(f"Received values from PLC: {values}")

            # Обновляем теги в In-Memory Bus
            for reg_idx, tag_id in self.tag_map.items():
                if reg_idx < len(values):
                    raw_val = values[reg_idx]
                    tag = self.bus.get(tag_id)
                    if tag is None:
                        tag = Tag(id=tag_id)
                    tag.update_value(raw_val)
                    self.bus.publish(tag)
                    logger.debug(f"Updated Tag {tag.id} = {tag.value} [{tag.quality}]")

            return values
        else:
            logger.warning(f"Unexpected Function Code: {resp_fc}")
            return None

    def stop(self):
        """Остановка цикла опроса."""
        self._running = False

    async def run(self):
        self._running = True
        logger.info(f"Starting Polling Engine targeting {self.host}:{self.port} (interval={self.interval}s)")
        
        while self._running:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info(f"Connected to PLC at {self.host}:{self.port} successfully.")
                
                while self._running:
                    await self._read_registers(writer, reader)
                    
                    self.transaction_id = (self.transaction_id + 1) % 65535
                    await asyncio.sleep(self.interval)
                    
            except (ConnectionRefusedError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
                logger.error(f"Connection lost or refused ({type(e).__name__}). Retrying in 3 seconds...")
                self._mark_all_tags_bad()
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                self._mark_all_tags_bad()
                await asyncio.sleep(3)

        logger.info("Polling Engine stopped.")


if __name__ == "__main__":
    engine = PollingEngine()
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        logger.info("Polling Engine stopped by user.")