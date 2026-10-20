from src.core.models import Tag

class PassThroughFilter:
     """Тестовая подмена фильтра — пропускает все значения без отсева."""
       
     def should_store(self, tag: Tag) -> bool:
         """Всегда возвращает True."""
         return True