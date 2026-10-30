import asyncio
from copy import deepcopy
from typing import Dict

from .models import Tag

from typing import Dict

from .models import Tag


class InMemoryBus:
    def __init__(self):
        self._tags: Dict[str, Tag] = {}
        self._subscribers: set[asyncio.Queue[Tag]] = set()

    def publish(self, tag: Tag) -> None:
        snapshot = deepcopy(tag)
        # Обновляем актуальное состояние
        self._tags[snapshot.id] = snapshot
        # Уведомляем подписчиков
        for queue in tuple(self._subscribers):
            queue.put_nowait(deepcopy(snapshot))

    def get(self, tag_id: str) -> Tag | None:
        tag = self._tags.get(tag_id)
        return deepcopy(tag) if tag is not None else None


    def get_all(self) -> Dict[str, Tag]:
        return deepcopy(self._tags)

    def subscribe(
        self,
        *,
        replay_current: bool = True,
    ) -> asyncio.Queue[Tag]:
        queue: asyncio.Queue[Tag] = asyncio.Queue()
        self._subscribers.add(queue)

        if replay_current:
            for tag in self._tags.values():
                queue.put_nowait(deepcopy(tag))

        return queue

    def unsubscribe(self, queue: asyncio.Queue[Tag]) -> None:
        self._subscribers.discard(queue)


