"""Изолированный запуск REST API для лабораторного IPC-эксперимента.

Polling Engine намеренно отключён: для проверки HTTP/TCP не требуется ПЛК.
API, InMemoryBus, StorageService и SQLite остаются штатными компонентами проекта.
Перед запуском можно задать SCADA_DB_PATH, чтобы использовать отдельную БД.
"""

from src.api.main import bus, create_app
from src.core.models import Quality, Tag

# Демонстрационный тег появляется в /api/tags. StorageService получает его
# через replay_current и сохраняет в учебную SQLite-базу при старте приложения.
LAB_TAG_ID = "LAB_DEMO_TEMP"
bus.publish(Tag(id=LAB_TAG_ID, value=23.5, quality=Quality.GOOD))

app = create_app(enable_polling=False)
