
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
    """
    Заглушка Modbus-клиента.

    Мы НЕ тестируем сам Modbus-протокол (это зона Студента 1 и
    test_modbus.py). Мы тестируем слой принятия решений: ДОШЛА ли
    команда до клиента или Safety Limits отбила её раньше.
    """

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
    """
    Собирает изолированное приложение:
      * enable_polling=False — чтобы тесты не пытались соединиться с PLC;
      * своя БД в tmp_path — тесты не мешают друг другу;
      * injected FakeCommandService — наблюдаем, что дошло до «PLC».
    """
    fake_commands = commands or FakeCommandService()

    app = create_app(
        bus_instance=InMemoryBus(),
        database_instance=Database(str(tmp_path / "test.db")),
        deadband_instance=DeadbandFilter(threshold=0.0),
        commands=fake_commands,  # type: ignore[arg-type]
        safety_limits_instance=safety_limits
        or SafetyLimits.from_mapping(
            {40001: (20, 90)},
            allow_unknown=False,
        ),
        enable_polling=False,
    )

    return TestClient(app), fake_commands


WRITE_URL = "/api/commands/write-register"


# ---------------------------------------------------------------------------
# 1. Главный safety-контракт: опасные значения не доходят до PLC
# ---------------------------------------------------------------------------


class TestSafetyBlocksWrites:
    def test_value_above_limit_rejected_and_not_sent_to_plc(self, tmp_path):
        """
        Уставка 150 при лимите [20..90].
        Проверяем ДВА факта:
          * HTTP 422 — оператор получил понятный отказ;
          * fake.calls == [] — команда физически не ушла в PLC.
        Второй факт важнее первого: именно он означает «железо в безопасности».
        """
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001, "value": 150})

        assert response.status_code == 422
        assert fake.calls == []

    def test_value_below_limit_rejected_and_not_sent_to_plc(self, tmp_path):
        """Ниже минимума — тоже опасно (например, остановка насоса)."""
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001, "value": 10})

        assert response.status_code == 422
        assert fake.calls == []

    def test_unknown_register_blocked_in_whitelist_mode(self, tmp_path):
        """
        allow_unknown=False: попытка писать в регистр 40002,
        которого нет в whitelist -> отказ, PLC не тронут.
        """
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40002, "value": 50})

        assert response.status_code == 422
        assert fake.calls == []

    def test_rejection_detail_explains_reason(self, tmp_path):
        """
        В ответе должна быть причина (регистр, диапазон),
        а не абстрактное «error» — так фронтенд/оператор поймёт,
        какую уставку можно задать.
        """
        client, _ = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001, "value": 150})

        detail = response.json()["detail"]
        assert "40001" in detail
        assert "20" in detail and "90" in detail


# ---------------------------------------------------------------------------
# 2. Валидные команды проходят сквозь все проверки
# ---------------------------------------------------------------------------


class TestValidCommands:
    def test_valid_command_returns_200_and_reaches_plc(self, tmp_path):
        """75 ∈ [20..90] -> 200 OK, мок-PLC получил ровно одну запись."""
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001, "value": 75})

        assert response.status_code == 200
        assert fake.calls == [(40001, 75)]

        body = response.json()
        assert body["status"] == "ok"
        assert body["command"] == "write_register"
        assert body["value"] == 75

    @pytest.mark.parametrize("value", [20, 90])
    def test_boundary_values_accepted(self, tmp_path, value):
        """Границы диапазона включительны — частая ошибка off-by-one."""
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001, "value": value})

        assert response.status_code == 200
        assert fake.calls == [(40001, value)]


# ---------------------------------------------------------------------------
# 3. Ошибки транспорта PLC отделяются от ошибок политики
# ---------------------------------------------------------------------------


class TestPLCFailure:
    def test_plc_connection_error_maps_to_502(self, tmp_path):
        """
        Команда ВАЛИДНА по лимитам, но PLC недоступен.
        Это 502 Bad Gateway (проблема нижележащего сервиса),
        а НЕ 422 — иначе оператор подумает, что ему запретили уставку.
        """
        client, fake = make_client(
            tmp_path,
            commands=FakeCommandService(
                fail_with=PLCCommandError("Cannot connect to PLC"),
            ),
        )

        response = client.post(WRITE_URL, json={"register": 40001, "value": 75})

        assert response.status_code == 502
        # Команда всё равно была передана в клиент (решение принято, связь сломалась)
        assert fake.calls == [(40001, 75)]

    def test_502_body_does_not_leak_internals(self, tmp_path):
        """Наружу — общая фраза; детали остаются в логах сервера."""
        client, _ = make_client(
            tmp_path,
            commands=FakeCommandService(
                fail_with=PLCCommandError("socket timeout on fd=12"),
            ),
        )

        response = client.post(WRITE_URL, json={"register": 40001, "value": 75})

        assert "socket timeout" not in str(response.json())


# ---------------------------------------------------------------------------
# 4. Валидация схемы запроса (Pydantic) — до бизнес-логики
# ---------------------------------------------------------------------------


class TestRequestValidation:
    def test_out_of_uint16_range_rejected_by_schema(self, tmp_path):
        """value=70000 > 65535 — отсекается ещё до Safety Limits."""
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001, "value": 70000})

        assert response.status_code == 422
        assert fake.calls == []

    def test_negative_register_rejected(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": -1, "value": 50})

        assert response.status_code == 422
        assert fake.calls == []

    def test_missing_field_rejected(self, tmp_path):
        client, fake = make_client(tmp_path)

        response = client.post(WRITE_URL, json={"register": 40001})

        assert response.status_code == 422
        assert fake.calls == []

    def test_non_integer_value_rejected(self, tmp_path):
        """Защита от 'семьдесят пять' из фронтенда."""
        client, fake = make_client(
            tmp_path,
        )

        response = client.post(
            WRITE_URL, json={"register": 40001, "value": "seventy-five"},
        )

        assert response.status_code == 422
        assert fake.calls == []


# ---------------------------------------------------------------------------
# 5. Порядок проверок: safety BEFORE write (порядок важен!)
# ---------------------------------------------------------------------------


class TestCheckOrdering:
    def test_safety_checked_before_plc_even_when_plc_available(self, tmp_path):
        """
        Специальный тест-страж: даже если PLC полностью доступен
        (мок никогда не падает), опасная команда не проходит.
        Это защищает от будущего рефакторинга, в котором кто-то
        переставит validate() ПОСЛЕ write_register().
        """
        client, fake = make_client(tmp_path)

        dangerous = [(40001, 0), (40001, 91), (40001, 10000), (40002, 50)]

        for register, value in dangerous:
            response = client.post(
                WRITE_URL, json={"register": register, "value": value},
            )
            assert response.status_code == 422, f"{register}={value} пропущено!"

        assert fake.calls == [], "Ни одна опасная команда не могла дойти до PLC"