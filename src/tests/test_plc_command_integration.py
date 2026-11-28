from __future__ import annotations

import asyncio

import pytest

from src.api.commands import PLCCommandService
from src.simulator.virtual_plc import VirtualPLC


@pytest.mark.asyncio
async def test_fc06_writes_value_to_virtual_plc_register():
    """Проверяет настоящий Modbus TCP FC06 между клиентом и VirtualPLC.

    В отличие от API-тестов с FakeCommandService, здесь запускается
    настоящий TCP-сервер VirtualPLC и используется настоящий
    PLCCommandService. Сервер слушает случайный свободный порт.
    """
    plc = VirtualPLC(host="127.0.0.1", port=0)
    plc._running = True

    server = await asyncio.start_server(
        plc._handle_client,
        host="127.0.0.1",
        port=0,
    )
    server_port = server.sockets[0].getsockname()[1]

    command_service = PLCCommandService(
        host="127.0.0.1",
        port=server_port,
        timeout=2.0,
    )

    try:
        # В VirtualPLC регистр 4 — уставка температуры, начальное значение 800.
        assert plc.registers[4] == 800

        # FC06: записываем 850, то есть 85.0 °C при масштабе x10.
        await command_service.write_register(
            register=4,
            value=850,
        )

        # Проверяем изменение реального массива регистров симулятора.
        assert plc.registers[4] == 850

        # Соседние регистры не должны измениться.
        assert plc.registers[0] == 750
        assert plc.registers[1] == 210
        assert plc.registers[2] == 1
        assert plc.registers[3] == 0

    finally:
        plc._running = False
        server.close()
        await server.wait_closed()
