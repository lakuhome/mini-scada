import asyncio
import struct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VirtualPLC")

class VirtualPLC:
    def __init__(self, host: str = "127.0.0.1", port: int = 5020):
        self.host = host
        self.port = port
        # Имитация оперативной памяти ПЛК (100 регистров по 16 бит)
        self.registers = [0] * 100 
        self._running = False

    async def _simulate_physics(self):
        """
        Изолированный цикл, который 'живет' своей жизнью.
        Меняет значения в регистрах, имитируя датчики.
        """
        logger.info("Physics engine started...")
        while self._running:
            # Пример: Имитация счетчика в нулевом регистре
            self.registers[0] += 1 
            if self.registers[0] > 65535: # Ограничение 16-битного целого
                self.registers[0] = 0
            
            # Здесь можно добавить шум, синусоиды или имитацию поломок
            await asyncio.sleep(1.0) # Цикл ПЛК (скан-цикл)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Низкоуровневая работа с сетью: двухступенчатое чтение фрейма Modbus TCP.
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"Connection established from {addr}")

        try:
            while self._running:
                # ШАГ 1: Читаем ровно 7 байт заголовка (MBAP Header)
                try:
                    mbap_bytes = await reader.readexactly(7)
                except asyncio.IncompleteReadError:
                    # Клиент разорвал соединение или прислал огрызок
                    break
                
                # Распаковываем шапку (>HHHB = Big-Endian, 2 байта, 2 байта, 2 байта, 1 байт)
                transaction_id, protocol_id, length, unit_id = struct.unpack('>HHHB', mbap_bytes)
                
                logger.debug(f"MBAP Header -> TX: {transaction_id}, Proto: {protocol_id}, Len: {length}, Unit: {unit_id}")

                # ШАГ 2: Вычисляем длину полезной нагрузки и дочитываем ее
                # length указывает количество байт ПОСЛЕ самого поля length. 
                # 1 байт (Unit ID) мы уже прочитали, значит осталось length - 1
                pdu_length = length - 1
                
                if pdu_length > 0:
                    pdu_bytes = await reader.readexactly(pdu_length)
                else:
                    logger.warning("Empty PDU received")
                    continue
                
                # ШАГ 3: Парсим само «письмо» (PDU - Protocol Data Unit)
                # Первый байт полезной нагрузки - это ВСЕГДА код функции (команда)
                function_code = pdu_bytes[0]
                
                logger.info(f"Received Function Code: {function_code}")

                # Здесь будет ветвление логики (маршрутизация)
                if function_code == 3:
                    # Команда 03: Чтение Holding Registers (Read Holding Registers)
                    # Следующие 2 байта - начальный адрес регистра
                    # Еще 2 байта - количество запрашиваемых регистров
                    start_address, register_count = struct.unpack('>HH', pdu_bytes[1:5])
                    logger.info(f"Client wants to read {register_count} registers starting from {start_address}")
                    
                    # --- НАЧАЛО БЛОКА ФОРМИРОВАНИЯ ОТВЕТА ---

                    # 1. Защита от выхода за пределы памяти (Segmentation fault в миниатюре)
                    if start_address + register_count > len(self.registers):
                        logger.error(f"Memory access violation: Address {start_address} is out of bounds")
                        # В реальном Modbus здесь упаковывается пакет с ошибкой 02 (Illegal Data Address)
                        continue
                    
                    # 2. Читаем данные из виртуальной памяти (срез массива)
                    requested_values = self.registers[start_address : start_address + register_count]
                    
                    # 3. Упаковываем значения регистров в сырые байты
                    # Если просят 5 регистров, динамически генерируем трафарет '>5H'
                    data_format = f'>{register_count}H'
                    # Звездочка * распаковывает список в отдельные аргументы для функции pack
                    packed_data = struct.pack(data_format, *requested_values)
                    
                    # 4. Высчитываем размер поля Length для заголовка
                    byte_count = register_count * 2
                    # Length = Unit ID (1 байт) + Function Code (1 байт) + Byte Count (1 байт) + размер данных
                    response_length = 1 + 1 + 1 + byte_count
                    
                    # 5. Упаковываем новую шапку и начало PDU
                    # Трафарет: 3 числа типа short (H) и 3 числа типа char (B)
                    header_format = '>HHHBBB'
                    header_bytes = struct.pack(
                        header_format,
                        transaction_id,  # Копируем из запроса
                        protocol_id,     # Копируем из запроса
                        response_length, # Наша вычисленная длина
                        unit_id,         # Копируем из запроса
                        function_code,   # 03
                        byte_count       # Количество байт данных
                    )
                    
                    # 6. Склеиваем шапку и полезную нагрузку
                    full_response = header_bytes + packed_data
                    
                    # 7. Записываем в сокет и проталкиваем в сеть
                    writer.write(full_response)
                    await writer.drain() # Команда ОС немедленно отправить буфер
                    
                    logger.info(f"Successfully replied with {register_count} registers. Total bytes sent: {len(full_response)}")
                    
                    # --- КОНЕЦ БЛОКА ФОРМИРОВАНИЯ ОТВЕТА ---
                    
                else:
                    logger.warning(f"Unsupported function code: {function_code}")
                    # В реальном Modbus здесь нужно отправить пакет с ошибкой (Exception Response)

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
            # Запускаем сетевой сервер и физику конкурентно
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