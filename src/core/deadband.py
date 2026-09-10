from .models import Tag


class DeadbandFilter:
    def __init__(self, threshold: float):
        self.threshold = threshold
        self._last_values: dict[str, float] = {}

    def should_store(self, tag: Tag) -> bool:
        if tag.id not in self._last_values:
            self._last_values[tag.id] = tag.value
            return True

        last_value = self._last_values[tag.id]

        if abs(tag.value - last_value) >= self.threshold:
            self._last_values[tag.id] = tag.value
            return True

        return False