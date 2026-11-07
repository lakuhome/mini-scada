from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.commands import PLCCommandError
from src.api.main import create_app
from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.safety import SafetyLimits
from src.storage.database import Database


class FakeCommandService:
    """Заглушка Modbus-клиента для проверки REST API и Safety Limits."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.calls: list[tuple[int, int]] = []
        self.fail_with = fail_with

    async def write_register(self, register: int, value: int) -> None:
        self.calls.append((register, value))

        if self.fail_with is not None:
            raise self.fail_with


def make_client(
    tmp_path,
    *,
    commands: FakeCommandService | None = None,
    safety_limits: SafetyLimits | None = None,
) -> tuple[TestClient, FakeCommandService]:
    """Создаёт изолированное приложение для API-тестов.

    Если safety_limits не переданы, create_app использует настоящую
    DEFAULT_SAFETY_LIMITS из src/api/main.py. Это важно: тестируем
    конфигурацию приложения, а не отдельную тестовую политику.
    """
    fake_commands = commands or FakeCommandService()

    app = create_app(
        bus_instance=InMemoryBus(),
        database_instance=Database(str(tmp_path / "test.db")),
        deadband_instance=DeadbandFilter(threshold=0.0),
        commands=fake_commands,  # type: ignore[arg-type]
        safety_limits_instance=safety_limits,
        enable_polling=False,
    )

    return TestClient(app), fake_commands


WRITE_URL = "/api/commands/write-register"


class TestDefaultSafetyLimits:
    """Проверяем именно конфигурацию Safety Limits по умолчанию."""

    def test_valid_setpoint_allowed(self, tmp_path):
        client, fake = make_client(tmp_path)

        with client:
            response = client.post(
                WRITE_URL,
                json={"register": 4, "value": 800},
            )

        assert response.status_code == 200
        assert fake.calls == [(4, 800)]

    @pytest.mark.parametrize(
        ("register", "value"),
        [
            (4, 199),
            (4, 901),
            (5, 800),
        ],
    )
    def test_unsafe_commands_rejected(
        self,
        tmp_path,
        register: int,
        value: int,
    ):
        client, fake = make_client(tmp_path)

        with client:
            response = client.post(
                WRITE_URL,
                json={"register": register, "value": value},
            )

        assert response.status_code == 422
        assert fake.calls == []


class TestSafetyBlocksWrites:
    def test_value_above_limit_rejected_and_not_sent_to_plc(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 901},
        )

        assert response.status_code == 422
        assert fake.calls == []

    def test_value_below_limit_rejected_and_not_sent_to_plc(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 199},
        )

        assert response.status_code == 422
        assert fake.calls == []

    def test_unknown_register_blocked_in_whitelist_mode(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 5, "value": 500},
        )

        assert response.status_code == 422
        assert fake.calls == []

    def test_rejection_detail_explains_reason(self, tmp_path):
        client, _ = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 901},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "4" in detail
        assert "200" in detail
        assert "900" in detail


class TestValidCommands:
    def test_valid_command_returns_200_and_reaches_plc(self, tmp_path):
        """750 означает 75.0 °C и находится в диапазоне [200..900]."""
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 750},
        )

        assert response.status_code == 200
        assert fake.calls == [(4, 750)]

        body = response.json()
        assert body["status"] == "ok"
        assert body["command"] == "write_register"
        assert body["value"] == 750

    @pytest.mark.parametrize("value", [200, 900])
    def test_boundary_values_accepted(self, tmp_path, value: int):
        """Минимум и максимум диапазона включены."""
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": value},
        )

        assert response.status_code == 200
        assert fake.calls == [(4, value)]


class TestPLCFailure:
    def test_plc_connection_error_maps_to_502(self, tmp_path):
        client, fake = make_client(
            tmp_path,
            commands=FakeCommandService(
                fail_with=PLCCommandError("Cannot connect to PLC"),
            ),
        )

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 750},
        )

        assert response.status_code == 502
        # Safety пропустил команду; транспортный клиент был вызван.
        assert fake.calls == [(4, 750)]

    def test_502_body_does_not_leak_internals(self, tmp_path):
        client, _ = make_client(
            tmp_path,
            commands=FakeCommandService(
                fail_with=PLCCommandError("socket timeout on fd=12"),
            ),
        )

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 750},
        )

        assert response.status_code == 502
        assert "socket timeout" not in str(response.json())


class TestRequestValidation:
    def test_out_of_uint16_range_rejected_by_schema(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": 70000},
        )

        assert response.status_code == 422
        assert fake.calls == []

    def test_negative_register_rejected(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": -1, "value": 50},
        )

        assert response.status_code == 422
        assert fake.calls == []

    def test_missing_field_rejected(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4},
        )

        assert response.status_code == 422
        assert fake.calls == []

    def test_non_integer_value_rejected(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(
            WRITE_URL,
            json={"register": 4, "value": "seventy-five"},
        )

        assert response.status_code == 422
        assert fake.calls == []


class TestCheckOrdering:
    def test_safety_checked_before_plc_even_when_plc_available(self, tmp_path):
        client, fake = make_client(tmp_path)

        dangerous_commands = [
            (4, 199),
            (4, 901),
            (4, 10000),
            (5, 500),
        ]

        for register, value in dangerous_commands:
            response = client.post(
                WRITE_URL,
                json={"register": register, "value": value},
            )
            assert response.status_code == 422, (
                f"Команда register={register}, value={value} была пропущена"
            )

        assert fake.calls == [], "Запрещённые команды не должны доходить до PLC"
