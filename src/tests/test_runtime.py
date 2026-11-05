import asyncio
from contextlib import suppress

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.core.bus import InMemoryBus
from src.core.models import Tag
from src.core.safety import SafetyLimits
from src.da.polling_engine import PollingEngine
from src.simulator.virtual_plc import VirtualPLC
from src.storage.database import Database


async def wait_until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_real_plc_command_archive_and_recovery(tmp_path):
    plc = VirtualPLC(port=0)
    plc_task = asyncio.create_task(plc.run())
    await wait_until(lambda: plc._server is not None)
    port = plc._server.sockets[0].getsockname()[1]
    bus = InMemoryBus()
    database = Database(str(tmp_path / 'history.db'))
    poller = PollingEngine(port=port, bus=bus, interval=0.02, timeout=0.1, retry_interval=0.02)
    api = create_app(bus_instance=bus, database_instance=database, polling_engine=poller,
                     plc_port=port, safety_limits_instance=SafetyLimits.from_mapping({4: (200, 1000)}, allow_unknown=False))
    try:
        async with api.router.lifespan_context(api):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url='http://test') as client:
                await wait_until(lambda: bus.get('Boiler_Temp_01').quality == 'GOOD')
                response = await client.post('/api/tags/Temp_Setpoint_01/setpoint', json={'value': 85.5})
                assert response.status_code == 200
                assert plc.registers[4] == 855
                await wait_until(lambda: bus.get('Temp_Setpoint_01').value == 855)
                await wait_until(lambda: bus.get('Temp_Setpoint_01').timestamp > response.json()['acknowledged_at'])
                assert (await client.post('/api/tags/Temp_Setpoint_01/setpoint', json={'value': 101})).status_code == 422
                assert (await client.post('/api/tags/Temp_Setpoint_01/setpoint', json={'value': 85.55})).status_code == 422
                assert (await client.post('/api/tags/Boiler_Temp_01/setpoint', json={'value': 80})).status_code == 422
                assert plc.registers[4] == 855
                plc.stop()
                plc_task.cancel()
                with suppress(asyncio.CancelledError):
                    await plc_task
                await wait_until(lambda: bus.get('Boiler_Temp_01').quality == 'BAD')
                assert (await client.get('/api/health')).status_code == 200
                plc = VirtualPLC(port=port)
                plc_task = asyncio.create_task(plc.run())
                await wait_until(lambda: bus.get('Boiler_Temp_01').quality == 'GOOD')
        # Shutdown drains the event queue before closing SQLite. Reopening must retain both states.
        async with Database(str(tmp_path / 'history.db')) as reopened:
            history = await reopened.get_history('Boiler_Temp_01')
            assert any(tag.quality == 'BAD' for tag in history)
            assert history[0].quality == 'GOOD'
            setpoints = await reopened.get_history('Temp_Setpoint_01')
            assert any(tag.value == 855 and tag.quality == 'GOOD' for tag in setpoints)
    finally:
        plc.stop()
        plc_task.cancel()
        await asyncio.gather(plc_task, return_exceptions=True)


def test_websocket_snapshot_multiple_clients_and_json_safety(tmp_path):
    bus = InMemoryBus()
    bus.publish(Tag(id='Boiler_Temp_01', value=750, quality='GOOD'))
    api = create_app(bus_instance=bus, database_instance=Database(str(tmp_path / 'ws.db')), enable_polling=False)
    with TestClient(api) as client:
        with client.websocket_connect('/ws/tags') as first:
            with client.websocket_connect('/ws/tags') as second:
                assert first.receive_json()['tags'][0]['value'] == 750
                assert second.receive_json()['tags'][0]['quality'] == 'GOOD'
            client.portal.call(bus.publish, Tag(id='Boiler_Temp_01', value=float('nan'), quality='BAD'))
            for _ in range(4):
                snapshot = first.receive_json()
                if snapshot['tags'][0]['quality'] == 'BAD':
                    break
            assert snapshot['tags'][0]['value'] is None
            assert snapshot['tags'][0]['quality'] == 'BAD'


def test_catalog_denies_writes_by_default_and_serves_panel(tmp_path):
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'index.html').write_text('<title>Operator panel</title>', encoding='utf-8')
    api = create_app(database_instance=Database(str(tmp_path / 'api.db')), enable_polling=False, web_dir=web,
                     safety_limits_instance=SafetyLimits.from_mapping({}, allow_unknown=False))
    with TestClient(api) as client:
        assert 'Operator panel' in client.get('/').text
        meta = client.get('/api/catalog').json()['Temp_Setpoint_01']
        assert meta['divisor'] == 10 and meta['writable'] is False
        assert client.post('/api/tags/Temp_Setpoint_01/setpoint', json={'value': 80}).status_code == 422
        assert client.get('/api/tags/x/history?start=nan').status_code == 422


def test_simulator_temperature_approaches_setpoint():
    plc = VirtualPLC()
    plc.registers[4] = 900
    for step in range(10):
        plc._step_physics(step)
    assert 750 < plc.registers[0] < 900


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['delay', 'disconnect'])
async def test_simulator_fault_controls_and_poller_recovery(fault):
    plc = VirtualPLC(port=0, response_delay=0.2 if fault == 'delay' else 0,
                     disconnect_every=1 if fault == 'disconnect' else 0)
    server_task = asyncio.create_task(plc.run())
    await wait_until(lambda: plc._server is not None)
    bus = InMemoryBus()
    poller = PollingEngine(port=plc._server.sockets[0].getsockname()[1], bus=bus,
                           interval=0.01, timeout=0.05, retry_interval=0.01)
    bus.publish(Tag(id='Boiler_Temp_01', value=750, quality='GOOD'))
    events = bus.subscribe(replay_current=False)
    poll_task = asyncio.create_task(poller.run())
    try:
        async with asyncio.timeout(5):
            while True:
                tag = await events.get()
                if tag.id == 'Boiler_Temp_01' and tag.quality == 'BAD':
                    break
            plc.response_delay = 0
            plc.disconnect_every = 0
            while True:
                tag = await events.get()
                if tag.id == 'Boiler_Temp_01' and tag.quality == 'GOOD':
                    break
    finally:
        bus.unsubscribe(events)
        poller.stop()
        poll_task.cancel()
        plc.stop()
        server_task.cancel()
        await asyncio.gather(poll_task, server_task, return_exceptions=True)
