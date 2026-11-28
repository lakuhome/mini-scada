import asyncio

import pytest

from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.models import Tag
from src.storage.service import StorageService


class FlakyDatabase:
    def __init__(self):
        self.fail_next = True
        self.saved = []

    async def save_tag(self, tag):
        if self.fail_next:
            self.fail_next = False
            raise OSError("simulated SQLite write failure")
        self.saved.append(tag)


def test_deadband_state_is_not_committed_when_database_save_fails():
    async def scenario():
        database = FlakyDatabase()
        deadband = DeadbandFilter(threshold=1.0)
        service = StorageService(InMemoryBus(), deadband, database)
        tag = Tag(id="TEMP_TEST", value=20.0, quality="GOOD")

        with pytest.raises(OSError, match="simulated SQLite write failure"):
            await service.process_tag(tag)

        # Тот же тег должен быть допущен к повторной попытке: первая запись
        # не прошла, поэтому базовая точка Deadband не должна была обновиться.
        assert await service.process_tag(tag) is True
        assert len(database.saved) == 1

        # После успешного commit повтор такого же значения фильтруется.
        assert await service.process_tag(tag) is False

    asyncio.run(scenario())


def test_deadband_commits_only_after_successful_database_save():
    async def scenario():
        database = FlakyDatabase()
        database.fail_next = False
        deadband = DeadbandFilter(threshold=1.0)
        service = StorageService(InMemoryBus(), deadband, database)

        assert await service.process_tag(Tag(id="TEMP_TEST", value=20.0, quality="GOOD")) is True
        assert await service.process_tag(Tag(id="TEMP_TEST", value=20.4, quality="GOOD")) is False
        assert await service.process_tag(Tag(id="TEMP_TEST", value=21.0, quality="GOOD")) is True
        assert len(database.saved) == 2

    asyncio.run(scenario())
