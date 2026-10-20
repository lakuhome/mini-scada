from __future__ import annotations

import logging
import math
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query

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
)

from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter

from src.storage.database import Database
from src.storage.service import StorageService


logger = logging.getLogger(__name__)


bus = InMemoryBus()

deadband = DeadbandFilter(
    threshold=1.0,
)

database = Database()

storage_service = StorageService(
    bus=bus,
    deadband=deadband,
    database=database,
)

command_service = PLCCommandService()


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
) -> FastAPI:

    current_bus = (
        bus_instance
        if bus_instance is not None
        else bus
    )

    current_deadband = (
        deadband_instance
        if deadband_instance is not None
        else deadband
    )

    current_database = (
        database_instance
        if database_instance is not None
        else database
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
        else command_service
    )

    @asynccontextmanager
    async def lifespan(
        _: FastAPI,
    ) -> AsyncIterator[None]:

        await current_storage.database.connect()

        # Если у тебя StorageService / Data Acquisition имеют фоновые задачи
        # и они должны запускаться вместе с API, добавь их запуск и остановку
        # сюда. Например:
        #
        # task = asyncio.create_task(current_storage.start())
        # try:
        #     yield
        # finally:
        #     task.cancel()
        #     await asyncio.gather(task, return_exceptions=True)
        #     await current_storage.database.close()

        try:
            yield

        finally:
            await current_storage.database.close()

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
    ) -> HistoryResponse:

        history = await current_storage.get_history(
            tag_id=tag_id,
            limit=limit,
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
            command="write_register",
            register_address=(
                command.register_address
            ),
            value=command.value,
        )

    return api


app = create_app()