import asyncio
import struct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VirtualPLC")

class VirtualPLC:
    def __init__(self, host: str = "127.0.0.1", port: int = 5020):
        self.host = host
        self.port = port
        self.registers = [0] * 100 
        self._running = False

    async def _simulate_physics(self):
        """
        Изолированный цикл, который 'живет' своей жизнью.
        Меняет значения в регистрах, имитируя датчики.
        """
        logger.info("Physics engine started...")
        while self._running:
            self.registers[0] += 1 
            if self.registers[0] > 65535:
                self.registers[0] = 0
            
            await asyncio.sleep(1.0)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Низкоуровневая работа с сетью: двухступенчатое чтение фрейма Modbus TCP.
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"Connection established from {addr}")

        try:
            while self._running:
                try:
                    mbap_bytes = await reader.readexactly(7)
                except asyncio.IncompleteReadError:
                    break

                transaction_id, protocol_id, length, unit_id = struct.unpack('>HHHB', mbap_bytes)
                
                logger.debug(f"MBAP Header -> TX: {transaction_id}, Proto: {protocol_id}, Len: {length}, Unit: {unit_id}")

                pdu_length = length - 1
                
                if pdu_length > 0:
                    pdu_bytes = await reader.readexactly(pdu_length)
                else:
                    logger.warning("Empty PDU received")
                    continue

                function_code = pdu_bytes[0]
                
                logger.info(f"Received Function Code: {function_code}")

                if function_code == 3:
                    start_address, register_count = struct.unpack('>HH', pdu_bytes[1:5])
                    logger.info(f"Client wants to read {register_count} registers starting from {start_address}")

                    if start_address + register_count > len(self.registers):
                        logger.error(f"Memory access violation: Address {start_address} is out of bounds")
                        continue

                    requested_values = self.registers[start_address : start_address + register_count]
                    
                    data_format = f'>{register_count}H'
                    packed_data = struct.pack(data_format, *requested_values)
 
                    byte_count = register_count * 2
                    response_length = 1 + 1 + 1 + byte_count
                    
                    header_format = '>HHHBBB'
                    header_bytes = struct.pack(
                        header_format,
                        transaction_id, 
                        protocol_id,
                        response_length,
                        unit_id,
                        function_code,
                        byte_count
                    )

                    full_response = header_bytes + packed_data
                    
                    writer.write(full_response)
                    await writer.drain()
                    
                    logger.info(f"Successfully replied with {register_count} registers. Total bytes sent: {len(full_response)}")

                elif function_code == 6:
                    start_address, write_value = struct.unpack('>HH', pdu_bytes[1:5])
                    logger.info(f"Client wants to write value {write_value} to register {start_address}")

                    if start_address >= len(self.registers):
                        logger.error(f"Memory access violation: Address {start_address} is out of bounds")
                        continue

                    self.registers[start_address] = write_value
                    logger.info(f"Register {start_address} successfully updated to {write_value}")

                    response_length = 6 
                    
                    header_format = '>HHHBB'
                    header_bytes = struct.pack(
                        header_format,
                        transaction_id, 
                        protocol_id,
                        response_length,
                        unit_id,
                        function_code
                    )
                    
                    data_bytes = struct.pack('>HH', start_address, write_value)
                    
                    full_response = header_bytes + data_bytes
                    
                    writer.write(full_response)
                    await writer.drain()
                    
                    logger.info(f"Successfully replied to write command. Total bytes sent: {len(full_response)}")
                    
                else:
                    logger.warning(f"Unsupported function code: {function_code}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            logger.info(f"Connection closed for {addr}")
            writer.close()
            await writer.wait_closed()

    async def run(self):
        """Запуск сервера и физического движка"""
        self._running = True
        server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        
        addr = server.sockets[0].getsockname()
        logger.info(f"Virtual PLC listening on {addr}")

        async with server:
            await asyncio.gather(
                server.serve_forever(),
                self._simulate_physics()
            )

if __name__ == "__main__":
    plc = VirtualPLC(port=5020)
    try:
        asyncio.run(plc.run())
    except KeyboardInterrupt:
        logger.info("PLC stopped by user.")