import time
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Quality(str, Enum):
    """
    Качество данных тега (OPC-подобная модель).

    Наследуемся от str, чтобы:
      * значения оставались JSON-сериализуемыми без кастомных энкодеров;
      * старые строковые сравнения вида tag.quality == "GOOD" продолжали работать;
      * SQLite писал привычный TEXT без изменений схемы.
    """

    GOOD = "GOOD"
    BAD = "BAD"

    @classmethod
    def parse(cls, value: "Quality | str") -> "Quality":
        """
        Приводит строку ("good", Quality.BAD) к члену enum.
        Нужен для чтения из БД и внешних источников, где тип не гарантирован.
        """
        if isinstance(value, cls):
            return value

        try:
            return cls(str(value).strip().upper())

        except ValueError as exc:
            raise ValueError(
                f"Unknown quality value: {value!r} "
                f"(expected one of {[q.value for q in cls]})"
            ) from exc


@dataclass
class Tag:
    id: str                              # Уникальное имя тега (например, "Boiler_Temp_01")
    value: Any = 0.0                     # Актуальное значение (int, float, bool)
    timestamp: float = field(default_factory=time.time)  # Unix-время
    quality: Quality = Quality.BAD       # GOOD или BAD

    def __post_init__(self) -> None:
        # Принимаем и строки ("GOOD"), и enum — обратная совместимость
        # со всем существующим кодом и тестами.
        self.quality = Quality.parse(self.quality)

    def update_value(self, new_value: Any) -> None:
        """
        Обновляет значение тега при успешном чтении данных с ПЛК.
        """
        # Базовая защита от битых данных (None, NaN, Infinity)
        if new_value is None or (
            isinstance(new_value, float)
            and (math.isnan(new_value) or math.isinf(new_value))
        ):
            self.set_bad_quality()
            return

        self.value = new_value
        self.quality = Quality.GOOD
        self.timestamp = time.time()

    def set_bad_quality(self) -> None:
        """
        Вызывается, когда Polling Engine теряет связь с оборудованием
        или получает ошибку по Modbus TCP.
        """
        self.quality = Quality.BAD
        self.timestamp = time.time()