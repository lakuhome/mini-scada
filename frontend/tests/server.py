"""Local browser-test fixture with explicit shutdown; never part of production API."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi.staticfiles import StaticFiles
from src.api.main import create_app
from src.core.bus import InMemoryBus
from src.core.safety import SafetyLimits
from src.da.polling_engine import PollingEngine
from src.simulator.virtual_plc import VirtualPLC


async def main():
    logging.getLogger().setLevel(logging.WARNING)
    plc = VirtualPLC(port=15020)
    bus = InMemoryBus()
    api = create_app(bus_instance=bus, plc_port=15020,
                     web_dir=Path(__file__).parent / 'no-static',
                     polling_engine=PollingEngine(port=15020, bus=bus, retry_interval=0.1),
                     safety_limits_instance=SafetyLimits.from_mapping({4: (200, 1000)}, allow_unknown=False))
    server = uvicorn.Server(uvicorn.Config(api, host='127.0.0.1', port=18000, log_level='warning',
                                           timeout_graceful_shutdown=3))

    @api.post('/__test/shutdown')
    async def shutdown():
        server.should_exit = True
        return {'status': 'stopping'}

    @api.post('/__test/plc/stop')
    async def stop_plc():
        plc.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return {'status': 'stopped'}

    @api.post('/__test/plc/start')
    async def start_plc():
        nonlocal plc, task
        if not task.done():
            return {'status': 'running'}
        plc = VirtualPLC(port=15020)
        task = asyncio.create_task(plc.run())
        return {'status': 'starting'}

    api.mount('/', StaticFiles(directory=Path(__file__).resolve().parents[1] / 'dist', html=True))

    task = asyncio.create_task(plc.run())
    try:
        await server.serve()
    finally:
        plc.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
