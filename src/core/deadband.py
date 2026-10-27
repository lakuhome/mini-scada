from .models import Tag


class DeadbandFilter:
    """
    Фильтр технологического шума датчиков (зона нечувствительности).

    Отсекает микроколебания технологических параметров, если абсолютное
    отклонение от последнего сохраненного значения меньше заданного порога.

    Attributes:
        threshold: Величина зоны нечувствительности в единицах измерения датчика.
    """

    def __init__(self, threshold: float):
        """
        Инициализирует фильтр с заданным порогом.

        Args:
            threshold: Порог нечувствительности (вещественное число >= 0).
        """
        self.threshold = threshold
        self._last_values: dict[str, tuple[float, str]] = {}

    def should_store(self, tag: Tag) -> bool:
        last_state = self._last_values.get(tag.id)

        if last_state is None:
            self._last_values[tag.id] = (
                tag.value,
                tag.quality,
            )
            return True

        last_value, last_quality = last_state

        # Изменение достоверности сохраняем независимо от deadband.
        if tag.quality != last_quality:
            self._last_values[tag.id] = (
                tag.value,
                tag.quality,
            )
            return True

        # Одинаковые значения отфильтровываются.
        if abs(tag.value - last_value) >= self.threshold:
            self._last_values[tag.id] = (
                tag.value,
                tag.quality,
            )
            return True

        return False