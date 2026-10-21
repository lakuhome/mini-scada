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
        self._last_values: dict[str, float] = {}

    def should_store(self, tag: Tag) -> bool:
        """
        Определяет необходимость сохранения отсчета тега в базу данных.

        Args:
            tag: Объект измерения Tag с полями id, value, timestamp, quality.

        Returns:
            bool: True, если отсчет подлежит сохранению; False, если отсчет является шумом.
        """
        if not isinstance(tag, Tag):
            raise TypeError(f"Ожидается объект Tag, получен {type(tag).__name__}")

        # Аварийные события (BAD) сохраняются в архив безусловно
        if getattr(tag, 'quality', None) == "BAD":
            self._last_values[tag.id] = tag.value
            return True

        if tag.id not in self._last_values:
            self._last_values[tag.id] = tag.value
            return True

        last_value = self._last_values[tag.id]

        if abs(tag.value - last_value) >= self.threshold:
            self._last_values[tag.id] = tag.value
            return True

        return False