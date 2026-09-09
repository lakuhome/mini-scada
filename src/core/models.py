import time
import math
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Tag:
    id: str            # Уникальное имя тега (например, "Boiler_Temp_01")
    value: Any = 0.0   # Актуальное значение (int, float, bool)
    timestamp: float = field(default_factory=time.time) # Unix-время
    quality: str = "BAD" # "GOOD" или "BAD"

    def update_value(self, new_value: Any) -> None:
        """
        Обновляет значение тега при успешном чтении данных с ПЛК.
        """
        # Базовая защита от битых данных (None или NaN)
        if new_value is None or (isinstance(new_value, float) and math.isnan(new_value)):
            self.set_bad_quality()
            return

        self.value = new_value
        self.quality = "GOOD"
        self.timestamp = time.time()

    def set_bad_quality(self) -> None:
        """
        Вызывается, когда Polling Engine теряет связь с оборудованием 
        или получает ошибку по Modbus TCP.
        """
        self.quality = "BAD"
        self.timestamp = time.time()