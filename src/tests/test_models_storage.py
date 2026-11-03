"""


  1. Quality — Enum GOOD/BAD вместо свободной строки:
     * парсинг из строк/enum, регистронезависимость;
     * обратная совместимость (str-наследование: JSON, == "GOOD");
     * Tag.update_value / set_bad_quality работают с enum.

  2. Защита от NaN/Infinity при записи в SQLite:
     * value REAL NOT NULL не принимает NaN/NULL -> пишем 0.0 + quality=BAD;
     * история после round-trip остаётся JSON-сериализуемой.

  3. get_history с параметрами start/end (временной диапазон):
     * границы включительны;
     * фильтрация + limit применяются вместе;
     * API /api/tags/{id}/history пробрасывает start/end и
       валидирует start <= end.
"""

from __future__ import annotations

import asyncio
import json
import math

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.models import Quality, Tag
from src.storage.database import Database


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def run(coro):
    """Синхронный запуск async-кода без pytest-asyncio (избегаем его багов)."""
    return asyncio.run(coro)


def make_client(tmp_path):
    """
    Изолированное приложение: своя БД, без polling.

    ВАЖНО: возвращаем кортеж (client, database) — тесты должны писать
    историю ЧЕРЕЗ ТОТ ЖЕ экземпляр Database, который использует приложение.
    Иначе получаем два независимых соединения к одному файлу и гонку
    «записал — не вижу» (особенно на Windows).
    """
    database = Database(str(tmp_path / "test.db"))

    app = create_app(
        bus_instance=InMemoryBus(),
        database_instance=database,   # <- ОДИН объект и для приложения, и для теста
        deadband_instance=DeadbandFilter(threshold=0.0),
        enable_polling=False,
    )

    return TestClient(app), database


# ---------------------------------------------------------------------------
# 1. Quality enum
# ---------------------------------------------------------------------------


class TestQualityEnum:
    def test_values(self):
        """Фиксируем контракт: ровно два состояния GOOD/BAD."""
        assert Quality.GOOD.value == "GOOD"
        assert Quality.BAD.value == "BAD"

    def test_parse_from_string(self):
        assert Quality.parse("GOOD") is Quality.GOOD
        assert Quality.parse("BAD") is Quality.BAD

    def test_parse_is_case_insensitive_and_strips(self):
        """Внешние источники (БД, Modbus-статусы) могут прислать 'good '."""
        assert Quality.parse("good") is Quality.GOOD
        assert Quality.parse(" Bad ") is Quality.BAD

    def test_parse_enum_returns_same_member(self):
        assert Quality.parse(Quality.GOOD) is Quality.GOOD

    def test_parse_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown quality"):
            Quality.parse("SUSPECT")

    def test_backward_compatible_string_comparison(self):
        """
        КЛЮЧЕВОЙ тест обратной совместимости: старый код и тесты сравнивают
        tag.quality == "GOOD". Без str-наследования это сломалось бы везде.
        """
        tag = Tag(id="T", value=1.0, quality=Quality.GOOD)
        assert tag.quality == "GOOD"
        assert not tag.quality == "BAD"

    def test_json_serializable_without_custom_encoder(self):
        tag = Tag(id="T", value=1.0, quality=Quality.BAD)
        payload = json.dumps({"quality": tag.quality})
        assert payload == '{"quality": "BAD"}'

    def test_sqlite_text_roundtrip(self, tmp_path):
        """Enum должен сохраняться в колонку TEXT и читаться обратно."""
        database = Database(str(tmp_path / "q.db"))

        async def scenario():
            await database.connect()
            await database.save_tag(
                Tag(id="Q_Test", value=5.0, quality=Quality.GOOD),
            )
            history = await database.get_history("Q_Test")
            await database.close()
            return history

        history = run(scenario())

        assert len(history) == 1
        assert history[0].quality is Quality.GOOD


class TestTagWithQuality:
    def test_default_quality_is_bad(self):
        """Новый тег BAD по умолчанию: пока нет подтверждения из PLC."""
        tag = Tag(id="T", value=0.0)
        assert tag.quality is Quality.BAD

    def test_string_quality_coerced_in_post_init(self):
        """Конструктор принимает и строку — весь старый код не сломается."""
        tag = Tag(id="T", value=1.0, quality="GOOD")
        assert tag.quality is Quality.GOOD

    def test_invalid_string_quality_rejected_at_creation(self):
        with pytest.raises(ValueError, match="Unknown quality"):
            Tag(id="T", value=1.0, quality="MAYBE")

    def test_update_value_sets_good(self):
        tag = Tag(id="T", value=1.0)
        tag.update_value(42)
        assert tag.value == 42
        assert tag.quality is Quality.GOOD

    @pytest.mark.parametrize(
        "bad_value", [None, float("nan"), float("inf"), float("-inf")],
    )
    def test_update_value_rejects_bad_data(self, bad_value):
        """None/NaN/±Inf -> значение НЕ пишется, качество становится BAD."""
        tag = Tag(id="T", value=10.0, quality=Quality.GOOD)
        tag.update_value(bad_value)
        assert tag.quality is Quality.BAD
        # Старое значение сохранено — мусором не затираем
        assert tag.value == 10.0

    def test_set_bad_quality(self):
        tag = Tag(id="T", value=1.0, quality=Quality.GOOD)
        tag.set_bad_quality()
        assert tag.quality is Quality.BAD


# ---------------------------------------------------------------------------
# 2. Защита от NaN при записи в БД
# ---------------------------------------------------------------------------


class TestDatabaseNanGuard:
    def _roundtrip(self, tmp_path, tag):
        database = Database(str(tmp_path / "nan.db"))

        async def scenario():
            await database.connect()
            await database.save_tag(tag)
            history = await database.get_history(tag.id)
            await database.close()
            return history

        return run(scenario())

    def test_nan_saved_as_zero_with_bad_quality(self, tmp_path):
        """
        NaN нельзя положить в value REAL так, чтобы потом
        FastAPI не упал на json.dumps. Пишем 0.0 + BAD.
        """
        history = self._roundtrip(
            tmp_path,
            Tag(id="Broken", value=float("nan"), quality=Quality.GOOD),
        )

        assert len(history) == 1
        assert history[0].value == 0.0
        assert history[0].quality is Quality.BAD

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf")])
    def test_infinity_guarded_too(self, tmp_path, bad):
        history = self._roundtrip(
            tmp_path,
            Tag(id="InfTest", value=bad, quality=Quality.GOOD),
        )

        assert history[0].value == 0.0
        assert history[0].quality is Quality.BAD

    def test_non_numeric_value_guarded(self, tmp_path):
        """Мусор вроде 'abc' из битого парсера тоже не должен попасть в REAL."""
        history = self._roundtrip(
            tmp_path,
            Tag(id="StrVal", value="not-a-number", quality=Quality.GOOD),
        )

        assert history[0].value == 0.0
        assert history[0].quality is Quality.BAD

    def test_valid_value_untouched(self, tmp_path):
        history = self._roundtrip(
            tmp_path,
            Tag(id="Good", value=85.5, quality=Quality.GOOD),
        )

        assert history[0].value == 85.5
        assert history[0].quality is Quality.GOOD

    def test_saved_history_is_always_json_safe(self, tmp_path):
        """
        Главный инвариант: любое значение из истории можно отдать FastAPI.
        Раньше NaN долетал до response_model и ронял эндпоинт 500-й ошибкой.
        """
        self._roundtrip(
            tmp_path,
            Tag(id="JsonSafe", value=float("nan"), quality=Quality.GOOD),
        )

        database = Database(str(tmp_path / "nan.db"))

        async def read():
            await database.connect()
            history = await database.get_history("JsonSafe")
            await database.close()
            return history

        history = run(read())
        # Не должно бросить ValueError: Out of range float values...
        json.dumps([h.value for h in history])

    def test_nan_does_not_leak_into_api_response(self, tmp_path):
        """Сквозная проверка: save_tag(NaN) -> GET history -> валидный JSON."""
        client, database = make_client(tmp_path)   # <- та же БД, что у приложения

        async def seed():
            await database.connect()
            await database.save_tag(
                Tag(id="LeakTest", value=float("nan"), quality=Quality.GOOD),
            )
            # НЕ закрываем соединение: приложение читает через него же

        run(seed())

        response = client.get("/api/tags/LeakTest/history")

        assert response.status_code == 200
        record = response.json()["history"][0]
        assert record["value"] == 0.0
        assert record["quality"] == "BAD"


# ---------------------------------------------------------------------------
# 3. get_history со start/end
# ---------------------------------------------------------------------------


class TestHistoryRange:
    @pytest.fixture()
    def seeded_db(self, tmp_path):
        """10 записей с timestamp 100..1000 (шаг 100) для tag 'R'."""
        database = Database(str(tmp_path / "range.db"))

        async def seed():
            await database.connect()
            for i in range(1, 11):
                await database.save_tag(
                    Tag(
                        id="R",
                        value=float(i),
                        timestamp=i * 100.0,
                        quality=Quality.GOOD,
                    ),
                )
            await database.close()

        run(seed())
        return database

    def _get(self, db, **kwargs):
        async def read():
            await db.connect()
            rows = await db.get_history(**kwargs)
            await db.close()
            return rows

        return run(read())

    def test_no_filters_returns_all_newest_first(self, seeded_db):
        rows = self._get(seeded_db, tag_id="R", limit=100)

        assert len(rows) == 10
        assert rows[0].timestamp == 1000.0
        assert rows[-1].timestamp == 100.0

    def test_start_filters_lower_bound_inclusive(self, seeded_db):
        rows = self._get(seeded_db, tag_id="R", limit=100, start=500.0)

        timestamps = [r.timestamp for r in rows]
        assert min(timestamps) == 500.0   # граница включительно
        assert len(rows) == 6             # 500..1000

    def test_end_filters_upper_bound_inclusive(self, seeded_db):
        rows = self._get(seeded_db, tag_id="R", limit=100, end=300.0)

        assert max(r.timestamp for r in rows) == 300.0
        assert len(rows) == 3

    def test_start_and_end_window(self, seeded_db):
        rows = self._get(
            seeded_db, tag_id="R", limit=100, start=300.0, end=700.0,
        )

        assert sorted(r.timestamp for r in rows) == [
            300.0, 400.0, 500.0, 600.0, 700.0,
        ]

    def test_range_combined_with_limit(self, seeded_db):
        """limit берётся ПОСЛЕ фильтрации: newest-first внутри окна."""
        rows = self._get(
            seeded_db, tag_id="R", limit=2, start=300.0, end=700.0,
        )

        assert [r.timestamp for r in rows] == [700.0, 600.0]

    def test_empty_window_returns_empty_list(self, seeded_db):
        rows = self._get(seeded_db, tag_id="R", limit=100, start=2000.0)
        assert rows == []

    def test_start_greater_than_end_returns_empty(self, seeded_db):
        """На уровне БД это просто пустой результат (валидация — задача API)."""
        rows = self._get(
            seeded_db, tag_id="R", limit=100, start=700.0, end=300.0,
        )
        assert rows == []

    def test_other_tags_unaffected(self, seeded_db):
        rows = self._get(seeded_db, tag_id="OTHER", limit=100)
        assert rows == []


class TestHistoryApiRange:
    """start/end должны быть доступны через REST API."""

    def test_api_supports_start_end_params(self, tmp_path):
        client, database = make_client(tmp_path)

        async def seed():
            await database.connect()
            for i in (1, 2, 3, 4, 5):
                await database.save_tag(
                    Tag(
                        id="Api_R",
                        value=float(i),
                        timestamp=i * 100.0,
                        quality=Quality.GOOD,
                    ),
                )

        run(seed())

        response = client.get("/api/tags/Api_R/history?start=200&end=400")

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        assert sorted(r["timestamp"] for r in body["history"]) == [
            200.0, 300.0, 400.0,
        ]

    def test_api_rejects_start_after_end(self, tmp_path):
        """Логичная ошибка для оператора: интервал наоборот -> 422."""
        client, _ = make_client(tmp_path)

        response = client.get("/api/tags/Any_Tag/history?start=1000&end=500")

        assert response.status_code == 422
        assert "start" in response.json()["detail"]

    def test_api_limit_still_works_with_range(self, tmp_path):
        client, database = make_client(tmp_path)

        async def seed():
            await database.connect()
            for i in range(1, 6):
                await database.save_tag(
                    Tag(
                        id="Api_L",
                        value=float(i),
                        timestamp=i * 100.0,
                        quality=Quality.GOOD,
                    ),
                )

        run(seed())

        response = client.get("/api/tags/Api_L/history?limit=2&start=100")

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        assert [r["timestamp"] for r in body["history"]] == [500.0, 400.0]