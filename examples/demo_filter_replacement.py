"""
Демонстрация подмены реализации фильтра для потребителя StorageService.

Показывает, что один и тот же потребитель (StorageService) работает
как со штатным DeadbandFilter, так и с тестовой заглушкой PassThroughFilter
без изменения своего исходного кода (МДК.01.04 ПР № 2, Р4).
"""

from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.models import Tag
from src.storage.database import Database
from src.storage.service import StorageService


class PassThroughFilter:
    """Тестовая заглушка фильтра, пропускающая все значения без отсева."""

    def should_store(self, tag: Tag) -> bool:
        return True


def main():
    bus = InMemoryBus()
    db = Database("data/history.db")

    # Вариант 1: Штатный режим работы (фильтрация технологического шума)
    filter_prod = DeadbandFilter(threshold=0.5)
    service_prod = StorageService(bus=bus, deadband=filter_prod, database=db)

    # Вариант 2: Тестовый режим (сохранение абсолютно всех точек без отсева)
    filter_test = PassThroughFilter()
    service_test = StorageService(bus=bus, deadband=filter_test, database=db)

    print("Обе реализации успешно подключены к StorageService!")


if __name__ == "__main__":
    main()
