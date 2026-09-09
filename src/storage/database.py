import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Tuple
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from aiosqlite import connect

logger = logging.getLogger("Database")

class HistoryDatabase:
    def __init__(self, db_path: str = "scada_history.db"):
        self.db_path = Path(db_path)
        self._pool: Optional[sqlite3.Connection] = None  # Пул соединений
        self._lock = asyncio.Lock()
        self._init_database_sync()  # Синхронная инициализация (только при старте)
        logger.info(f"База данных инициализирована: {self.db_path}")
    
    def _init_database_sync(self):
        """Инициализация схемы (вызывается один раз при старте)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                name TEXT PRIMARY KEY,
                address INTEGER NOT NULL,
                description TEXT,
                unit TEXT,
                min_value REAL,
                max_value REAL,
                deadband REAL,
                safety_min REAL,
                safety_max REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tag_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL,
                value REAL NOT NULL,
                quality TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (tag_name) REFERENCES tags(name)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_tag_time 
            ON tag_history(tag_name, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_time 
            ON tag_history(timestamp DESC)
        """)
        
        # WAL режим для лучшей производительности
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        conn.commit()
        conn.close()
    
    async def _get_connection(self) -> sqlite3.Connection:
        """Получает подключение из пула (ленивая инициализация)"""
        if self._pool is None:
            self._pool = sqlite3.connect(
                self.db_path,
                check_same_thread=False  # Разрешаем использовать в разных потоках
            )
            self._pool.row_factory = sqlite3.Row
            self._pool.execute("PRAGMA journal_mode=WAL")
            self._pool.execute("PRAGMA synchronous=NORMAL")
        return self._pool
    
    def register_tag(self, tag):
        """Сохраняет метаданные тега (синхронно, вызывается редко)"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tags 
                (name, address, description, unit, min_value, max_value, deadband, safety_min, safety_max)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tag.name, tag.address, tag.description, tag.unit,
                tag.min_value, tag.max_value, tag.deadband,
                tag.safety_min, tag.safety_max
            ))
            conn.commit()
            logger.debug(f"Тег {tag.name} зарегистрирован в БД")
        finally:
            conn.close()
    
    async def save_value(self, tag_name: str, value: float, quality: str, 
                        timestamp: Optional[datetime] = None,
                        deadband: float = 0.0) -> bool:
        """
        Асинхронное сохранение значения с deadband-проверкой.
        Оптимизация: используем один запрос с подзапросом.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        async with self._lock:
            conn = await self._get_connection()
            cursor = conn.cursor()
            
            # Оптимизация: один запрос вместо двух
            if deadband > 0:
                cursor.execute("""
                    INSERT INTO tag_history (tag_name, value, quality, timestamp)
                    SELECT ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM tag_history 
                        WHERE tag_name = ?
                        ORDER BY timestamp DESC 
                        LIMIT 1
                        HAVING ABS(? - value) < ?
                    )
                """, (tag_name, value, quality, timestamp.isoformat(),
                      tag_name, value, deadband))
            else:
                cursor.execute("""
                    INSERT INTO tag_history (tag_name, value, quality, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (tag_name, value, quality, timestamp.isoformat()))
            
            conn.commit()
            return cursor.rowcount > 0
    
    async def save_values_batch(self, values: List[Tuple[str, float, str, datetime]]):
        """
        Батчевая запись нескольких значений (для высокой нагрузки).
        values: [(tag_name, value, quality, timestamp), ...]
        """
        async with self._lock:
            conn = await self._get_connection()
            cursor = conn.cursor()
            
            cursor.executemany("""
                INSERT INTO tag_history (tag_name, value, quality, timestamp)
                VALUES (?, ?, ?, ?)
            """, [(name, val, qual, ts.isoformat()) for name, val, qual, ts in values])
            
            conn.commit()
            logger.debug(f"Батчевая запись: {len(values)} значений")
    
    async def get_historical_data(self, tag_name: str, 
                                 start_time: datetime, 
                                 end_time: datetime,
                                 limit: Optional[int] = None) -> List[Dict]:
        """Асинхронное получение исторических данных"""
        async with self._lock:
            conn = await self._get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT tag_name, value, quality, timestamp 
                FROM tag_history 
                WHERE tag_name = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """
            
            params = [tag_name, start_time.isoformat(), end_time.isoformat()]
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            
            return [
                {
                    "tag_name": row["tag_name"],
                    "value": row["value"],
                    "quality": row["quality"],
                    "timestamp": row["timestamp"]
                }
                for row in cursor.fetchall()
            ]
    
    async def get_latest_value(self, tag_name: str) -> Optional[Dict]:
        """Асинхронное получение последнего значения"""
        async with self._lock:
            conn = await self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value, quality, timestamp 
                FROM tag_history 
                WHERE tag_name = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (tag_name,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "value": row["value"],
                    "quality": row["quality"],
                    "timestamp": row["timestamp"]
                }
            return None
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Асинхронная очистка старых данных"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        async with self._lock:
            conn = await self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM tag_history 
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Удалено {deleted_count} старых записей")
            
            return deleted_count
    
    async def close(self):
        """Закрытие пула соединений при завершении работы"""
        if self._pool:
            self._pool.close()
            self._pool = None
            logger.info("База данных закрыта")