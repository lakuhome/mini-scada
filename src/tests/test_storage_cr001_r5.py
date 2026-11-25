from __future__ import annotations

import asyncio
import sqlite3

import pytest

from src.api.main import create_app
from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.models import Tag
from src.storage.database import Database
from src.storage.service import StorageService


@pytest.mark.asyncio
async def test_r5_successful_save_updates_deadband_only_after_commit(tmp_path):
    db = Database(str(tmp_path / "success.db"))
    deadband = DeadbandFilter(threshold=1.0)
    service = StorageService(InMemoryBus(), deadband, db)
    tag = Tag(id="TEMP_R5", value=20.0, quality="GOOD")

    await db.connect()
    try:
        assert await service.process_tag(tag) is True
        assert await service.process_tag(Tag(id="TEMP_R5", value=20.4, quality="GOOD")) is False
        history = await db.get_history("TEMP_R5")
        assert len(history) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_r5_resource_acquisition_error_leaves_no_connection(tmp_path):
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("file blocks directory creation", encoding="utf-8")
    db = Database(str(blocker / "cannot-create.db"))

    with pytest.raises((FileExistsError, NotADirectoryError, OSError)):
        await db.connect()

    assert db._connection is None


@pytest.mark.asyncio
async def test_cr001_sqlite_write_failure_does_not_advance_deadband(tmp_path):
    db = Database(str(tmp_path / "write-failure.db"))
    deadband = DeadbandFilter(threshold=1.0)
    service = StorageService(InMemoryBus(), deadband, db)
    tag = Tag(id="TEMP_FAIL_ONCE", value=20.0, quality="GOOD")

    await db.connect()
    connection = await db._get_connection()
    await asyncio.to_thread(
        connection.execute,
        """CREATE TRIGGER reject_lab_tag BEFORE INSERT ON tag_history
           WHEN NEW.tag_id = 'TEMP_FAIL_ONCE'
           BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""",
    )
    await asyncio.to_thread(connection.commit)

    try:
        with pytest.raises(sqlite3.IntegrityError, match="simulated storage failure"):
            await service.process_tag(tag)

        # База отказала: повтор того же значения должен снова пройти фильтр.
        assert deadband.would_store(tag) is True

        await asyncio.to_thread(connection.execute, "DROP TRIGGER reject_lab_tag")
        await asyncio.to_thread(connection.commit)

        assert await service.process_tag(tag) is True
        history = await db.get_history("TEMP_FAIL_ONCE")
        assert len(history) == 1
        assert history[0].value == 20.0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_r5_early_shutdown_unsubscribes_storage_and_closes_database(tmp_path):
    bus = InMemoryBus()
    deadband = DeadbandFilter(threshold=1.0)
    db = Database(str(tmp_path / "shutdown.db"))
    storage = StorageService(bus, deadband, db)
    app = create_app(
        bus_instance=bus,
        storage=storage,
        database_instance=db,
        deadband_instance=deadband,
        enable_polling=False,
    )

    async with app.router.lifespan_context(app):
        assert db._connection is not None
        assert len(bus._subscribers) == 1

    assert db._connection is None
    assert len(bus._subscribers) == 0
