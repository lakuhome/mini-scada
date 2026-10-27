from src.core.bus import InMemoryBus
from src.core.models import Tag
from src.core.deadband import DeadbandFilter
from src.storage.database import Database
import asyncio
import logging

logger = logging.getLogger(__name__)


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

    async def process_tag(self, tag: Tag) -> bool:
        if not self.filter.should_store(tag):
            return False

        await self.database.save_tag(tag)

        return True

    async def run(self) -> None:
        queue = self.bus.subscribe(replay_current=True)

        try:
            while True:
                tag = await queue.get()

                try:
                    await self.process_tag(tag)

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logger.exception(
                        "Failed to process tag %s",
                        tag.id,
                    )

                finally:
                    queue.task_done()

        finally:
            self.bus.unsubscribe(queue)

    async def get_history(
        self,
        tag_id: str,
        limit: int = 100,
    ) -> list[Tag]:
        return await self.database.get_history(
            tag_id=tag_id,
            limit=limit,
        )