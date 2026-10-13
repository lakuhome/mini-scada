from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Iterable, Mapping


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegisterLimit:
    """
    Допустимый диапазон значения Modbus-регистра.

    Значения хранятся в единицах регистра (uint16), потому что
    команды управления (FC06/FC16) работают именно с регистрами.
    """

    min_value: int
    max_value: int

    def __post_init__(self) -> None:
        if self.min_value > self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) greater than "
                f"max_value ({self.max_value})"
            )

    def contains(self, value: int) -> bool:
        return self.min_value <= value <= self.max_value


class SafetyLimitError(ValueError):
    """
    Raised when a write command violates configured safety limits.

    Наследуется от ValueError, поэтому существующий маппинг
    ``ValueError -> HTTP 422`` в API продолжает работать.
    """


class SafetyLimits:
    """
    Реестр предохранителей для записей в PLC.

    Политика по неизвестным регистрам:
      * ``allow_unknown=True``  — регистр без лимита пропускается
        (режим совместимости / разработки).
      * ``allow_unknown=False`` — whitelist: писать можно только в
        явно разрешённые регистры. Для прода с реальным железом
        рекомендую именно этот режим.
    """

    def __init__(
        self,
        limits: Mapping[int, RegisterLimit] | None = None,
        *,
        allow_unknown: bool = True,
    ) -> None:
        self._limits: dict[int, RegisterLimit] = dict(limits or {})
        self.allow_unknown = allow_unknown

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[int, tuple[int, int]],
        *,
        allow_unknown: bool = True,
    ) -> SafetyLimits:
        return cls(
            {
                register: RegisterLimit(min_value=lo, max_value=hi)
                for register, (lo, hi) in raw.items()
            },
            allow_unknown=allow_unknown,
        )

    def validate(self, register: int, value: int) -> None:
        limit = self._limits.get(register)

        if limit is None:
            if not self.allow_unknown:
                raise SafetyLimitError(
                    f"Register {register} is not allowed by safety policy"
                )
            logger.debug(
                "No safety limit for register %s, allowing value %s",
                register,
                value,
            )
            return

        if not limit.contains(value):
            raise SafetyLimitError(
                f"Value {value} for register {register} is outside "
                f"safety range [{limit.min_value}, {limit.max_value}]"
            )

    def validate_many(
        self,
        pairs: Iterable[tuple[int, int]],
    ) -> None:
        """
        Для будущей FC16 (write multiple registers, Студент 1).
        Проверяет каждую пару (register, value).
        """
        for register, value in pairs:
            self.validate(register, value)