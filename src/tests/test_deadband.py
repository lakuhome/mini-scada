import time
import pytest
from src.core.models import Tag
from src.core.deadband import DeadbandFilter


def make_tag(tag_id: str = "TEMP_01", value: float = 0.0) -> Tag:
    """Вспомогательная фабрика тестовых тегов."""
    return Tag(
        id=tag_id,
        value=value,
        timestamp=time.time(),
        quality="GOOD",
    )


# --- Классы эквивалентности (Equivalence Partitioning) ---

def test_tc_db_01_first_value_initialization():
    """TC-DB-01: Первое измерение тега всегда записывается (инициализация базовой точки)."""
    filter_ = DeadbandFilter(threshold=0.5)
    assert filter_.should_store(make_tag("TEMP_01", 20.0)) is True


def test_tc_db_02_noise_filtered_positive():
    """TC-DB-02: Положительное микроколебание внутри зоны (+0.2 < 0.5) отсеивается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 20.0))
    assert filter_.should_store(make_tag("TEMP_01", 20.2)) is False


def test_tc_db_03_noise_filtered_negative():
    """TC-DB-03: Отрицательное микроколебание внутри зоны (-0.2 < 0.5) отсеивается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 20.0))
    assert filter_.should_store(make_tag("TEMP_01", 19.8)) is False


def test_tc_db_04_significant_increase():
    """TC-DB-04: Существенный рост значения (+1.5 > 0.5) записывается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 20.0))
    assert filter_.should_store(make_tag("TEMP_01", 21.5)) is True


def test_tc_db_05_significant_decrease():
    """TC-DB-05: Существенный спад значения (-1.5 > 0.5) записывается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 20.0))
    assert filter_.should_store(make_tag("TEMP_01", 18.5)) is True


def test_tc_db_06_zero_change():
    """TC-DB-06: Повторное идентичное значение (дельта 0.0) отсеивается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 20.0))
    assert filter_.should_store(make_tag("TEMP_01", 20.0)) is False


def test_tc_db_07_multiple_independent_tags():
    """TC-DB-07: Изоляция тегов — фильтрация одного тега не влияет на другой."""
    filter_ = DeadbandFilter(threshold=0.5)
    assert filter_.should_store(make_tag("TEMP_01", 10.0)) is True
    assert filter_.should_store(make_tag("PRESS_01", 2.0)) is True

    # Шум по температуре отсекается, скачок по давлению записывается
    assert filter_.should_store(make_tag("TEMP_01", 10.2)) is False
    assert filter_.should_store(make_tag("PRESS_01", 3.0)) is True


# --- Граничные значения (Boundary Value Analysis) ---
# База = 10.0, Порог = 0.5. Границы: delta = 0.49, 0.50, 0.51

def test_tc_db_08_boundary_just_below_positive():
    """TC-DB-08: Значение чуть ниже границы (+0.49 < 0.50) отсеивается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 10.0))
    assert filter_.should_store(make_tag("TEMP_01", 10.49)) is False


def test_tc_db_09_boundary_exact_threshold_positive():
    """TC-DB-09: Значение ровно на границе (+0.50 == 0.50) записывается (контракт >= threshold)."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 10.0))
    assert filter_.should_store(make_tag("TEMP_01", 10.50)) is True


def test_tc_db_10_boundary_just_above_positive():
    """TC-DB-10: Значение чуть выше границы (+0.51 > 0.50) записывается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 10.0))
    assert filter_.should_store(make_tag("TEMP_01", 10.51)) is True


def test_tc_db_11_boundary_just_below_negative():
    """TC-DB-11: Отрицательное изменение чуть ниже границы (-0.49 < 0.50) отсеивается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 10.0))
    assert filter_.should_store(make_tag("TEMP_01", 9.51)) is False


def test_tc_db_12_boundary_exact_threshold_negative():
    """TC-DB-12: Отрицательное изменение ровно на границе (-0.50 == 0.50) записывается."""
    filter_ = DeadbandFilter(threshold=0.5)
    filter_.should_store(make_tag("TEMP_01", 10.0))
    assert filter_.should_store(make_tag("TEMP_01", 9.50)) is True

# --- Подмена реализации (Р4 МДК.01.04 ПЗ2) ---

class PassThroughFilter:
    """Тестовая подмена фильтра — пропускает все значения."""
    
    def should_store(self, tag: Tag) -> bool:
        """Всегда возвращает True — все значения сохраняются."""
        return True


def test_passthrough_filter_always_returns_true():
    """PassThroughFilter пропускает все значения без фильтрации."""
    filter_ = PassThroughFilter()
    
    # Первое значение
    assert filter_.should_store(make_tag("TEMP_01", 20.0)) is True
    
    # Микроколебание — всё равно True
    assert filter_.should_store(make_tag("TEMP_01", 20.01)) is True
    
    # Идентичное значение — всё равно True
    assert filter_.should_store(make_tag("TEMP_01", 20.0)) is True
