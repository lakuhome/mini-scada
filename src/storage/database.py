from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any
import math

from src.core.models import Tag
from src.core.models import Quality, Tag


class Database:

    def __init__(self, db_path: str = "scada.db") -> None:
        self.db_path = Path(db_path)
        self._connection: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._connection is not None:
            return

        async with self._lock:
            if self._connection is not None:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = await asyncio.to_thread(
                sqlite3.connect,
                self.db_path,
                check_same_thread=False,
            )
            try:
                await asyncio.to_thread(connection.execute, "PRAGMA journal_mode=WAL")
                await asyncio.to_thread(connection.execute, "PRAGMA synchronous=NORMAL")
                await asyncio.to_thread(
                    connection.execute,
                    """
                    CREATE TABLE IF NOT EXISTS tag_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_id TEXT NOT NULL,
                        value REAL NOT NULL,
                        timestamp REAL NOT NULL,
                        quality TEXT NOT NULL
                    )
                    """,
                )
                await asyncio.to_thread(
                    connection.execute,
                    """
                    CREATE INDEX IF NOT EXISTS idx_tag_history_tag_timestamp
                    ON tag_history(tag_id, timestamp DESC, id DESC)
                    """,
                )
                await asyncio.to_thread(connection.commit)
            except Exception:
                await asyncio.to_thread(connection.close)
                raise
            self._connection = connection

    async def _get_connection(self) -> sqlite3.Connection:
        await self.connect()
        assert self._connection is not None
        return self._connection

    async def save_tag(self, tag: Tag) -> None:
        """
        Сохраняет тег в историю.

        Защита от NaN/Infinity: SQLite хранит REAL и молча принимает NaN,
        но JSON-сериализация (FastAPI) на таком значении упадёт с
        "Out of range float values are not JSON compliant".
        Поэтому битовое значение помечаем quality=BAD — «мусор» в истории
        честно отмечен как недостоверный.

        Колонка value — NOT NULL (схема уже в проде), поэтому вместо NULL
        пишем 0.0: любое приложение, читающее историю, обязано смотреть
        сначала на quality, и только потом брать value.
        """
        value: float
        quality = tag.quality

        try:
            value = float(tag.value)

        except (TypeError, ValueError):
            value = 0.0
            quality = Quality.BAD

        else:
            if math.isnan(value) or math.isinf(value):
                value = 0.0
                quality = Quality.BAD

        connection = await self._get_connection()
        async with self._lock:
            await asyncio.to_thread(
                connection.execute,
                """
                INSERT INTO tag_history
                    (tag_id, value, timestamp, quality)
                VALUES (?, ?, ?, ?)
                """,
                (tag.id, value, tag.timestamp, str(quality.value)),
            )
            await asyncio.to_thread(connection.commit)

    async def get_history(
        self,
        tag_id: str,
        limit: int = 100,
        start: float | None = None,
        end: float | None = None,
    ) -> list[Tag]:
        """
        Читает историю тега.

        Args:
            start: нижняя граница времени (unix, включительно).
            end: верхняя граница времени (unix, включительно).
        """
        if limit <= 0:
            return []

        connection = await self._get_connection()
        async with self._lock:
            rows = await asyncio.to_thread(
                self._fetch_history,
                connection,
                tag_id,
                limit,
                start,
                end,
            )

        return [
            Tag(
                id=row[0],
                value=row[1],
                timestamp=row[2],
                quality=Quality.parse(row[3]),
            )
            for row in rows
        ]

    @staticmethod
    def _fetch_history(
        connection: sqlite3.Connection,
        tag_id: str,
        limit: int,
        start: float | None = None,
        end: float | None = None,
    ) -> list[tuple[Any, ...]]:
        query = """
            SELECT tag_id, value, timestamp, quality
            FROM tag_history
            WHERE tag_id = ?
        """
        params: list[Any] = [tag_id]

        # Динамические условия — только из заранее известных констант,
        # значения всегда через placeholders (SQL injection невозможен).
        if start is not None:
            query += " AND timestamp >= ?"
            params.append(start)

        if end is not None:
            query += " AND timestamp <= ?"
            params.append(end)

        query += """
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """
        params.append(limit)

        cursor = connection.execute(query, params)
        try:
            return cursor.fetchall()
        finally:
            cursor.close()

    async def close(self) -> None:
        async with self._lock:
            if self._connection is not None:
                connection = self._connection
                self._connection = None
                await asyncio.to_thread(connection.close)

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
