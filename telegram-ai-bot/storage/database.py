import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

import aiosqlite
from config import settings

log = logging.getLogger(__name__)

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role       TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT    NOT NULL,
    tokens_est INTEGER DEFAULT 0,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT    NOT NULL,
    source     TEXT    NOT NULL DEFAULT 'extracted',   -- 'extracted' | 'manual'
    created_at TEXT    NOT NULL,
    UNIQUE(content)
);

CREATE TABLE IF NOT EXISTS kv_stats (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_facts_ts    ON facts(created_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    _conn: Optional[aiosqlite.Connection] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @classmethod
    async def init(cls) -> None:
        cls._conn = await aiosqlite.connect(settings.db_path, check_same_thread=False)
        cls._conn.row_factory = aiosqlite.Row
        await cls._conn.executescript(_SCHEMA)
        await cls._conn.commit()
        log.info("SQLite ready — %s", settings.db_path)

    @classmethod
    async def close(cls) -> None:
        if cls._conn:
            await cls._conn.close()

    # ── Messages ───────────────────────────────────────────────────────────

    @classmethod
    async def add_message(cls, role: str, content: str) -> None:
        tokens_est = len(content) // 4
        await cls._conn.execute(
            "INSERT INTO messages (role, content, tokens_est, created_at) VALUES (?,?,?,?)",
            (role, content, tokens_est, _now()),
        )
        await cls._conn.commit()

    @classmethod
    async def get_recent_history(cls, limit: int = 20) -> List[Dict]:
        cur = await cls._conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    @classmethod
    async def get_message_count(cls) -> int:
        cur = await cls._conn.execute("SELECT COUNT(*) AS c FROM messages")
        row = await cur.fetchone()
        return row["c"]

    @classmethod
    async def clear_history(cls) -> None:
        await cls._conn.execute("DELETE FROM messages")
        await cls._conn.commit()

    # ── Facts ──────────────────────────────────────────────────────────────

    @classmethod
    async def add_fact(cls, content: str, source: str = "extracted") -> bool:
        """Insert a fact. Returns True if newly inserted, False if duplicate."""
        try:
            await cls._conn.execute(
                "INSERT OR IGNORE INTO facts (content, source, created_at) VALUES (?,?,?)",
                (content.strip(), source, _now()),
            )
            await cls._conn.commit()
            cur = await cls._conn.execute("SELECT changes() AS c")
            row = await cur.fetchone()
            return row["c"] > 0
        except Exception as exc:
            log.error("add_fact error: %s", exc)
            return False

    @classmethod
    async def get_all_facts(cls) -> List[str]:
        cur = await cls._conn.execute(
            "SELECT content FROM facts ORDER BY created_at DESC"
        )
        rows = await cur.fetchall()
        return [r["content"] for r in rows]

    @classmethod
    async def delete_facts_by_keyword(cls, keyword: str) -> int:
        cur = await cls._conn.execute(
            "DELETE FROM facts WHERE content LIKE ?", (f"%{keyword}%",)
        )
        await cls._conn.commit()
        return cur.rowcount

    # ── KV stats ───────────────────────────────────────────────────────────

    @classmethod
    async def get_stat(cls, key: str, default: str = "0") -> str:
        cur = await cls._conn.execute(
            "SELECT value FROM kv_stats WHERE key=?", (key,)
        )
        row = await cur.fetchone()
        return row["value"] if row else default

    @classmethod
    async def set_stat(cls, key: str, value: str) -> None:
        await cls._conn.execute(
            "INSERT OR REPLACE INTO kv_stats (key, value) VALUES (?,?)", (key, value)
        )
        await cls._conn.commit()

    @classmethod
    async def increment_stat(cls, key: str, by: int = 1) -> int:
        val = int(await cls.get_stat(key, "0")) + by
        await cls.set_stat(key, str(val))
        return val
