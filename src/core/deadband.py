from .models import Tag


class DeadbandFilter:
    """Фильтр значимых изменений тегов.

    Для обычного использования доступны два этапа:
      1. would_store() проверяет необходимость архивирования без изменения состояния.
      2. mark_stored() обновляет базовую точку только после успешной записи.

    should_store() оставлен как совместимый одноступенчатый метод для участков,
    где решение не связано с внешним хранилищем. StorageService должен применять
    двухфазный интерфейс, чтобы ошибка SQLite не сдвигала базовую точку Deadband.
    """

    def __init__(self, threshold: float):
        if threshold < 0:
            raise ValueError("threshold must be >= 0")
        self.threshold = threshold
        self._last_values: dict[str, tuple[float, str]] = {}

    def would_store(self, tag: Tag) -> bool:
        """Возвращает решение фильтра, не изменяя последнее сохранённое состояние."""
        last_state = self._last_values.get(tag.id)

        if last_state is None:
            return True

        last_value, last_quality = last_state

        # Изменение качества архивируется независимо от величины изменения.
        if tag.quality != last_quality:
            return True

        return abs(tag.value - last_value) >= self.threshold

    def mark_stored(self, tag: Tag) -> None:
        """Фиксирует базовую точку после подтверждённого успешного сохранения."""
        self._last_values[tag.id] = (tag.value, tag.quality)

    def should_store(self, tag: Tag) -> bool:
        """Совместимый метод: проверить и сразу зафиксировать решение."""
        if not self.would_store(tag):
            return False
        self.mark_stored(tag)
        return True
