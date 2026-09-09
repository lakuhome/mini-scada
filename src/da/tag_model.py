from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from datetime import datetime, timezone
import math

# 1. Качество данных (Quality)
class Quality(Enum):
    GOOD = "GOOD"           # Данные актуальны и надежны
    BAD = "BAD"             # Ошибка связи или некорректные данные
    UNCERTAIN = "UNCERTAIN" # Данные есть, но есть сомнения (например, датчик требует калибровки)

# 2. Класс Тега
@dataclass
class Tag:
    name: str               # Уникальное имя, например "Boiler_Temp_1"
    address: int            # Адрес регистра в PLC (например, 0)
    description: str = ""   # Описание для человека
    unit: str = ""          # Единица измерения ("°C", "Bar")
    
    # Правила валидации
    min_value: float = 0.0
    max_value: float = 65535.0
    deadband: float = 0.0   # Мертвая зона: минимальное изменение, которое мы считаем значимым
    
    # Текущее состояние (заполняется во время работы)
    value: Any = 0.0
    quality: Quality = Quality.BAD # По умолчанию считаем, что связи нет
    timestamp: datetime = field(default_factory=datetime.utcnow)
    previous_value: Any = None
    
    def update_value(self, new_value: float, check_deadband: bool = True) -> bool:
        """
        Пытается обновить значение тега.
        Возвращает True, если значение РЕАЛЬНО изменилось (вышло за пределы deadband).
        Возвращает False, если изменение слишком маленькое и его можно игнорировать.
        """

        if new_value is None or (isinstance(new_value, float) and math.isnan(new_value)):
            self.quality = Quality.UNCERTAIN # или BAD
            return False

        # Если качество было BAD, мы обязаны принять первое же полученное значение
        if self.quality == Quality.BAD:
            self.previous_value = self.value
            self.value = new_value
            self.quality = Quality.GOOD
            self.timestamp = datetime.now(timezone.utc)
            return True
        
        # Проверка мертвой зоны (Deadband)
        if check_deadband and self.deadband > 0:
            change = abs(new_value - self.value)
            if change < self.deadband:
                # Изменение меньше мертвой зоны
                return False
        
        # Если мы здесь, значит изменение значимое. Обновляем данные.
        self.previous_value = self.value
        self.value = new_value
        self.timestamp = datetime.utcnow()
        return True
    
    def set_bad_quality(self):
        """Вызывается, когда Polling Engine теряет связь с PLC"""
        self.quality = Quality.BAD
        self.timestamp = datetime.utcnow()