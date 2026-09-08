# Контракт данных: Структура Тега (Layer 2)

Этот документ описывает единый формат данных (In-Memory Bus Schema), которым обмениваются модуль сбора данных (Студент 1) и модуль хранения/API (Студент 2).

## Структура объекта Tag

Каждый тег в системе представляет собой объект (или dataclass), содержащий следующие поля:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class Tag:
    id: str            # Уникальное имя тега (например, "Boiler_Temp_01")
    value: Any         # Актуальное значение (int, float, bool)
    timestamp: float   # Unix-время получения данных (time.time())
    quality: str       # Достоверность данных: "GOOD" или "BAD"