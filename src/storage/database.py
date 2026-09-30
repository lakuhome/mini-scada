from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from src.core.models import Tag


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
        connection = await self._get_connection()
        async with self._lock:
            await asyncio.to_thread(
                connection.execute,
                """
                INSERT INTO tag_history
                    (tag_id, value, timestamp, quality)
                VALUES (?, ?, ?, ?)
                """,
                (tag.id, float(tag.value), tag.timestamp, tag.quality),
            )
            await asyncio.to_thread(connection.commit)

    async def get_history(self, tag_id: str, limit: int = 100) -> list[Tag]:
        if limit <= 0:
            return []

        connection = await self._get_connection()
        async with self._lock:
            rows = await asyncio.to_thread(self._fetch_history, connection, tag_id, limit)

        return [
            Tag(
                id=row[0],
                value=row[1],
                timestamp=row[2],
                quality=row[3],
            )
            for row in rows
        ]

    @staticmethod
    def _fetch_history(
        connection: sqlite3.Connection,
        tag_id: str,
        limit: int,
    ) -> list[tuple[Any, ...]]:
        cursor = connection.execute(
            """
            SELECT tag_id, value, timestamp, quality
            FROM tag_history
            WHERE tag_id = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (tag_id, limit),
        )
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
