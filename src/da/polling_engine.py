import asyncio
import struct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PollingEngine")

class PollingEngine:
    def __init__(self, host: str = "127.0.0.1", port: int = 5020, interval: float = 1.0):
        self.host = host
        self.port = port
        self.interval = interval
        self._running = False
        self.transaction_id = 1
        
        # В будущем здесь появится In-Memory Bus, куда мы будем складывать результаты

    async def _read_registers(self, writer: asyncio.StreamWriter, reader: asyncio.StreamReader):
        """
        Формирует запрос (FC 03), отправляет его и читает ответ.
        """
        start_address = 0
        register_count = 5
        
        pdu_length = 5

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
            logger.info(f"Received values: {values}")
            return values
        else:
            logger.warning(f"Unexpected Function Code: {resp_fc}")
            return None

    async def run(self):
        self._running = True
        logger.info(f"Starting Polling Engine targeting {self.host}:{self.port}")
        
        while self._running:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to PLC successfully.")
                
                while self._running:
                    await self._read_registers(writer, reader)
                    
                    self.transaction_id = (self.transaction_id + 1) % 65535
                    await asyncio.sleep(self.interval)
                    
            except (ConnectionRefusedError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
                logger.error(f"Connection lost or refused ({type(e).__name__}). Retrying in 3 seconds...")
                # TODO: Пометить все теги в In-Memory Bus как BAD
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(3)

if __name__ == "__main__":
    engine = PollingEngine()
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        logger.info("Polling Engine stopped.")