import sqlite3
from pathlib import Path

from src.core.models import Tag


class Database:
    def __init__(self, db_path: str = "scada.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    quality TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def save_tag(self, tag: Tag) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO tag_history
                    (tag_id, value, timestamp, quality)
                VALUES (?, ?, ?, ?)
                """,
                (tag.id, tag.value, tag.timestamp, tag.quality),
            )
            connection.commit()

    def get_history(
        self,
        tag_id: str,
        limit: int = 100,
    ) -> list[Tag]:
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT tag_id, value, timestamp, quality
                FROM tag_history
                WHERE tag_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (tag_id, limit),
            ).fetchall()

        return [
            Tag(
                id=row[0],
                value=row[1],
                timestamp=row[2],
                quality=row[3],
            )
            for row in rows
        ]