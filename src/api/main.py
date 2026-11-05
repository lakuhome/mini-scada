from __future__ import annotations
import asyncio
import os
import logging
import math
import json
import time
from decimal import Decimal
from pathlib import Path
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from src.core.catalog import TAG_CATALOG
from src.da.polling_engine import PollingEngine


from src.api.commands import (
    PLCCommandError,
    PLCCommandService,
)

from src.api.schemas import (
    CommandResponse,
    HistoryResponse,
    TagResponse,
    TagsResponse,
    WriteRegisterRequest,
    SetpointRequest,
)

from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.safety import SafetyLimits
from src.storage.database import Database
from src.storage.service import StorageService


logger = logging.getLogger(__name__)

PLC_HOST = os.getenv(
    "SCADA_PLC_HOST",
    "127.0.0.1",
)

PLC_PORT = int(
    os.getenv("SCADA_PLC_PORT", "5020"),
)

POLL_INTERVAL = float(
    os.getenv("SCADA_POLL_INTERVAL", "1.0"),
)

DEFAULT_SAFETY_LIMITS = SafetyLimits.from_mapping(
    {int(key): tuple(value) for key, value in json.loads(os.getenv("SCADA_SAFETY_LIMITS", "{}")).items()},
    allow_unknown=False,
)

bus = InMemoryBus()

deadband = DeadbandFilter(
    threshold=1.0,
)

database = Database(
    os.getenv("SCADA_DB_PATH", "scada.db"),
)


def tag_to_response(tag) -> TagResponse:
    """
    Преобразует внутренний Tag в API-модель.

    Дополнительно защищает JSON-ответ от NaN/Infinity.
    """

    value = tag.value
    quality = tag.quality

    if isinstance(value, float) and (
        math.isnan(value) or math.isinf(value)
    ):
        value = None
        quality = "BAD"

    return TagResponse(
        id=tag.id,
        value=value,
        timestamp=tag.timestamp,
        quality=quality,
    )


def create_app(
    *,
    bus_instance: InMemoryBus | None = None,
    storage: StorageService | None = None,
    commands: PLCCommandService | None = None,
    database_instance: Database | None = None,
    deadband_instance: DeadbandFilter | None = None,
    polling_engine: PollingEngine | None = None,
    enable_polling: bool = True,
    plc_host: str = PLC_HOST,
    plc_port: int = PLC_PORT,
    poll_interval: float = POLL_INTERVAL,
    safety_limits_instance: SafetyLimits | None = None,
    web_dir: str | Path | None = None,
) -> FastAPI:

    if storage is not None and bus_instance is None:
        current_bus = storage.bus
    else:
        current_bus = (
            bus_instance
            if bus_instance is not None
            else bus
        )

    if storage is not None and storage.bus is not current_bus:
        raise ValueError(
            "StorageService and API must share the same InMemoryBus"
        )

    if storage is not None and database_instance is None:
        current_database = storage.database
    else:
        current_database = (
            database_instance
            if database_instance is not None
            else database
        )

    if storage is not None and storage.database is not current_database:
        raise ValueError(
            "StorageService and API must share the same Database"
        )

    current_deadband = (
        deadband_instance
        if deadband_instance is not None
        else deadband
    )

    current_storage = (
        storage
        if storage is not None
        else StorageService(
            bus=current_bus,
            deadband=current_deadband,
            database=current_database,
        )
    )


    current_commands = (
        commands
        if commands is not None
        else PLCCommandService(
            host=plc_host,
            port=plc_port,
        )
    )

    current_safety_limits = (
        safety_limits_instance
        if safety_limits_instance is not None
        else DEFAULT_SAFETY_LIMITS
    )

    current_poller = None

    if enable_polling:
        current_poller = (
            polling_engine
            if polling_engine is not None
            else PollingEngine(
                host=plc_host,
                port=plc_port,
                interval=poll_interval,
                bus=current_bus,
            )
        )

        if current_poller.bus is not current_bus:
            raise ValueError(
                "PollingEngine and API must share the same InMemoryBus"
            )

    @asynccontextmanager
    async def lifespan(
        _: FastAPI,
    ) -> AsyncIterator[None]:

        storage_task: asyncio.Task | None = None
        polling_task: asyncio.Task | None = None
        db_connected = False

        try:
            # 1. Подключаем БД.
            await current_database.connect()
            db_connected = True

            # 2. Запускаем архивный обработчик.
            storage_task = asyncio.create_task(
                current_storage.run(),
                name="scada-storage",
            )

            # Даём обработчику подписаться на шину.
            await asyncio.sleep(0)

            if storage_task.done():
                await storage_task

            # 3. Запускаем опросчик на той же шине.
            if current_poller is not None:
                polling_task = asyncio.create_task(
                    current_poller.run(),
                    name="scada-polling",
                )

            # Приложение готово к работе.
            yield

        finally:
            # 4. Прекращаем новые публикации.
            if current_poller is not None:
                current_poller.stop()

            # 5. Завершаем опросчик.
            if polling_task is not None:
                polling_task.cancel()

                await asyncio.gather(
                    polling_task,
                    return_exceptions=True,
                )

            try:
                # 6. Дожидаемся обработки очереди архива.
                if (
                    storage_task is not None
                    and not storage_task.done()
                ):
                    await current_storage.drain()

            except Exception:
                logger.exception(
                    "Failed to drain storage queue"
                )

            finally:
                # 7. Завершаем архивный обработчик.
                if storage_task is not None:
                    storage_task.cancel()

                    await asyncio.gather(
                        storage_task,
                        return_exceptions=True,
                    )

                # 8. Закрываем БД последней.
                if db_connected:
                    await current_database.close()

    api = FastAPI(
        title="Mini SCADA API",
        version="0.2.0",
        description=(
            "REST API for current telemetry, "
            "historical data and PLC control commands."
        ),
        lifespan=lifespan,
    )

    @api.get(
        "/api/health",
        tags=["system"],
    )
    async def health() -> dict[str, str]:

        return {
            "status": "ok",
        }

    @api.get(
        "/api/tags",
        response_model=TagsResponse,
        tags=["tags"],
    )
    async def get_current_tags() -> TagsResponse:

        tags = [
            tag_to_response(tag)
            for tag in current_bus.get_all().values()
        ]

        tags.sort(
            key=lambda tag: tag.id,
        )

        return TagsResponse(
            count=len(tags),
            tags=tags,
        )

    @api.get(
        "/api/tags/{tag_id}",
        response_model=TagResponse,
        tags=["tags"],
    )
    async def get_current_tag(
        tag_id: str,
    ) -> TagResponse:

        tag = current_bus.get(
            tag_id,
        )

        if tag is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tag '{tag_id}' not found",
            )

        return tag_to_response(tag)

    @api.get(
        "/api/tags/{tag_id}/history",
        response_model=HistoryResponse,
        tags=["history"],
    )

    async def get_tag_history(
        tag_id: str,
        limit: int = Query(
            default=100,
            ge=1,
            le=1000,
            description="Maximum number of records",
        ),
        start: float | None = Query(
            default=None,
            description="Unix timestamp, inclusive lower bound",
        ),
        end: float | None = Query(
            default=None,
            description="Unix timestamp, inclusive upper bound",
        ),
    ) -> HistoryResponse:

        if any(bound is not None and not math.isfinite(bound) for bound in (start, end)):
            raise HTTPException(status_code=422, detail="Time bounds must be finite")
        if start is not None and end is not None and start > end:
            raise HTTPException(
                status_code=422,
                detail="'start' must be less than or equal to 'end'",
            )

        history = await current_storage.get_history(
            tag_id=tag_id,
            limit=limit,
            start=start,
            end=end,
        )

        history = history or []

        return HistoryResponse(
            tag_id=tag_id,
            count=len(history),
            history=[
                tag_to_response(tag)
                for tag in history
            ],
        )

    @api.post(
        "/api/commands/write-register",
        response_model=CommandResponse,
        tags=["commands"],
    )
    async def write_register(
        command: WriteRegisterRequest,
    ) -> CommandResponse:

        try:

            current_safety_limits.validate(
                register=command.register_address,
                value=command.value,
            )

            await current_commands.write_register(
                register=command.register_address,
                value=command.value,
            )

        except ValueError as exc:

            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except PLCCommandError as exc:

            logger.warning(
                "PLC write-register failed: "
                "register=%s value=%s error=%s",
                command.register_address,
                command.value,
                exc,
            )

            raise HTTPException(
                status_code=502,
                detail="PLC command failed",
            ) from exc

        return CommandResponse(
            status="ok",
            acknowledged_at=time.time(),
            command="write_register",
            register_address=(
                command.register_address
            ),
            value=command.value,
        )

    @api.get("/api/catalog")
    async def catalog():
        result = {}
        for tag_id, meta in TAG_CATALOG.items():
            limit = current_safety_limits.get_limit(meta["register"])
            result[tag_id] = {
                **meta,
                "writable": limit is not None,
                "min": limit.min_value / meta["divisor"] if limit else None,
                "max": limit.max_value / meta["divisor"] if limit else None,
            }
        return result

    @api.post("/api/tags/{tag_id}/setpoint", response_model=CommandResponse)
    async def setpoint(tag_id: str, command: SetpointRequest):
        meta = TAG_CATALOG.get(tag_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="Unknown tag")
        raw = Decimal(str(command.value)) * meta["divisor"]
        if raw != raw.to_integral_value() or not 0 <= raw <= 65535:
            raise HTTPException(status_code=422, detail="Value cannot be represented by this register")
        return await write_register(WriteRegisterRequest(register=meta["register"], value=int(raw)))

    @api.websocket("/ws/tags")
    async def telemetry(websocket: WebSocket):
        await websocket.accept()

        async def send_snapshots():
            while True:
                tags = [tag_to_response(tag).model_dump(mode="json")
                        for tag in current_bus.get_all().values()]
                await asyncio.wait_for(websocket.send_json({
                    "type": "snapshot", "server_time": time.time(), "tags": tags,
                }), timeout=3.0)
                await asyncio.sleep(0.5)

        async def receive_disconnect():
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(send_snapshots()), asyncio.create_task(receive_disconnect())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, OSError, asyncio.TimeoutError):
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with suppress(WebSocketDisconnect, RuntimeError, OSError, asyncio.TimeoutError):
                await asyncio.wait_for(websocket.close(), timeout=1.0)

    dist = Path(web_dir or os.getenv("SCADA_WEB_DIR", str(Path(__file__).resolve().parents[2] / "frontend" / "dist")))
    if dist.is_dir():
        api.mount("/", StaticFiles(directory=dist, html=True), name="web")

    return api


app = create_app()
