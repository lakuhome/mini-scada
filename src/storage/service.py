from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.storage.database import Database


class StorageService:
    def __init__(
        self,
        bus: InMemoryBus,
        deadband: DeadbandFilter,
        database: Database,
    ):
        self.bus = bus
        self.deadband = deadband
        self.database = database

    async def process_tag(self, tag_id: str) -> bool:
        tag = self.bus.get(tag_id)

        if tag is None:
            return False

        if not self.deadband.should_store(tag):
            return False

        await self.database.save_tag(tag)

        return True