from __future__ import annotations

import pytest

from src.core.safety import (
    RegisterLimit,
    SafetyLimitError,
    SafetyLimits,
)


# ---------------------------------------------------------------------------
# RegisterLimit
# ---------------------------------------------------------------------------


class TestRegisterLimit:
    def test_contains_within_range(self):
        """Значения внутри диапазона (включая границы) допустимы."""
        limit = RegisterLimit(min_value=0, max_value=100)

        assert limit.contains(0)      # нижняя граница включительно
        assert limit.contains(50)     # середина
        assert limit.contains(100)    # верхняя граница включительно

    def test_contains_outside_range(self):
        """Значения за пределами диапазона запрещены."""
        limit = RegisterLimit(min_value=10, max_value=20)

        assert not limit.contains(9)
        assert not limit.contains(21)
        assert not limit.contains(-100)

    def test_single_point_limit(self):
        """Диапазон из одной точки легален (например, уставка = 50)."""
        limit = RegisterLimit(min_value=50, max_value=50)

        assert limit.contains(50)
        assert not limit.contains(49)
        assert not limit.contains(51)

    def test_min_greater_than_max_raises(self):
        """
        Инвариант: min_value не может быть больше max_value.
        Проверяем на этапе создания объекта — «fail fast»,
        чтобы конфигурационная опечатка упала при старте, а не при команде.
        """
        with pytest.raises(ValueError, match="min_value"):
            RegisterLimit(min_value=100, max_value=50)

    def test_is_frozen(self):
        """
        frozen dataclass: лимиты нельзя изменить после создания.
        Защита от случайной порчи конфигурации в рантайме.
        """
        limit = RegisterLimit(min_value=0, max_value=100)

        with pytest.raises(Exception):
            limit.max_value = 1000  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SafetyLimits.validate
# ---------------------------------------------------------------------------


class TestSafetyLimitsValidate:
    def _limits(self) -> SafetyLimits:
        """
        Конфигурация как на реальном объекте:
          регистр 40001 — уставка температуры котла, 20..90 градусов;
          регистр 40002 — скорость насоса, 0..1500 об/мин.
        """
        return SafetyLimits.from_mapping(
            {
                40001: (20, 90),
                40002: (0, 1500),
            },
            allow_unknown=True,
        )

    def test_valid_value_passes(self):
        """Корректная уставка проходит без исключения."""
        self._limits().validate(register=40001, value=75)

    @pytest.mark.parametrize("value", [19, 91, 1000])
    def test_out_of_range_blocked(self, value):
        """
        Опасные значения блокируются.
        19 — ниже минимума, 91 и 1000 — перегрев. Именно такие
        команды никогда не должны дойти до PLC.
        """
        with pytest.raises(SafetyLimitError):
            self._limits().validate(register=40001, value=value)

    def test_error_message_contains_context(self):
        """
        Сообщение об ошибке должно содержать регистр, значение и диапазон —
        оператор по логу должен понять, ПОЧЕМУ команду отклонили.
        """
        with pytest.raises(
            SafetyLimitError,
            match=r"register 40001.*outside safety range \[20, 90\]",
        ):
            self._limits().validate(register=40001, value=150)

    def test_boundary_values_pass(self):
        """Граничные значения (20 и 90) — допустимы, это часть диапазона."""
        limits = self._limits()
        limits.validate(register=40001, value=20)
        limits.validate(register=40001, value=90)

    def test_safety_limit_error_is_value_error(self):
        """
        Контракт с API: SafetyLimitError наследует ValueError,
        потому что в main.py стоит обработчик `except ValueError -> 422`.
        Если кто-то изменит базовый класс — тест упадёт и предупредит.
        """
        assert issubclass(SafetyLimitError, ValueError)


# ---------------------------------------------------------------------------
# Политика неизвестных регистров
# ---------------------------------------------------------------------------


class TestUnknownRegisterPolicy:
    def test_allow_unknown_true_passes(self):
        """Режим разработки: регистр без лимита пропускается."""
        limits = SafetyLimits(limits={}, allow_unknown=True)
        limits.validate(register=55555, value=123)

    def test_allow_unknown_false_blocks(self):
        """
        Whitelist-режим (продакшен): писать можно ТОЛЬКО в явно
        разрешённые регистры. Неизвестный адрес = отказ.
        """
        limits = SafetyLimits.from_mapping(
            {40001: (0, 100)},
            allow_unknown=False,
        )

        with pytest.raises(SafetyLimitError, match="not allowed"):
            limits.validate(register=40002, value=50)

    def test_whitelist_still_allows_known_registers(self):
        """Whitelist не ломает легальные команды по известным регистрам."""
        limits = SafetyLimits.from_mapping(
            {40001: (0, 100)},
            allow_unknown=False,
        )
        limits.validate(register=40001, value=50)

    def test_default_policy_is_permissive(self):
        """
        Фиксируем текущее поведение по умолчанию (allow_unknown=True),
        чтобы его изменение было осознанным и отражено в тесте.
        """
        limits = SafetyLimits()
        assert limits.allow_unknown is True


# ---------------------------------------------------------------------------
# validate_many (задел под FC16 — пакетную запись)
# ---------------------------------------------------------------------------


class TestValidateMany:
    def test_all_valid_passes(self):
        limits = SafetyLimits.from_mapping(
            {40001: (0, 100), 40002: (0, 100)},
            allow_unknown=False,
        )
        limits.validate_many([(40001, 50), (40002, 80)])

    def test_one_bad_pair_blocks_whole_batch(self):
        """
        Атомарность политики: если ХОТЬ ОДНА пара в пакете FC16 опасна —
        блокируется весь пакет. Частичная запись в PLC недопустима.
        """
        limits = SafetyLimits.from_mapping(
            {40001: (0, 100), 40002: (0, 100)},
            allow_unknown=False,
        )

        with pytest.raises(SafetyLimitError):
            limits.validate_many([(40001, 50), (40002, 500)])

    def test_empty_batch_is_noop(self):
        """Пустой пакет не должен падать."""
        SafetyLimits(allow_unknown=False).validate_many([])