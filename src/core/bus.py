from typing import Dict

from .models import Tag


class InMemoryBus:
    def __init__(self):
        self._tags: Dict[str, Tag] = {}

    def publish(self, tag: Tag) -> None:
        self._tags[tag.id] = tag

    def get(self, tag_id: str) -> Tag | None:
        return self._tags.get(tag_id)

    def get_all(self) -> Dict[str, Tag]:
        return self._tags.copy()