import logging
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import aiosqlite
from config import settings

log = logging.getLogger(__name__)

_SQLITE_SCHEMA = """
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
    source     TEXT    NOT NULL DEFAULT 'extracted',
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

_PG_DDL = [
    """
CREATE TABLE IF NOT EXISTS messages (
    id         BIGSERIAL PRIMARY KEY,
    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    tokens_est INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL
)
""",
    """
CREATE TABLE IF NOT EXISTS facts (
    id         BIGSERIAL PRIMARY KEY,
    content    TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'extracted',
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE(content)
)
""",
    """
CREATE TABLE IF NOT EXISTS kv_stats (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
""",
    "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_facts_ts ON facts (created_at DESC)",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _postgres_ssl_context_verify() -> ssl.SSLContext:
    """``sslmode=verify-ca`` / ``verify-full``: check server cert (Mozilla CA bundle)."""
    import certifi

    return ssl.create_default_context(cafile=certifi.where())


def _postgres_ssl_context_require() -> ssl.SSLContext:
    """``sslmode=require`` (and similar): TLS encryption without server cert verification.

    Matches PostgreSQL/libpq semantics. Supabase session pooler chains often fail
    strict public-CA verification; ``require`` is what their dashboard URIs use.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _asyncpg_pool_kwargs(dsn: str) -> Dict[str, Any]:
    """
    Build asyncpg.create_pool kwargs from DATABASE_URL.

    Passing user/password/host explicitly avoids URI quirks (encoded ``@`` in
    passwords, query params) that can still bite ``asyncpg``/libpq on some hosts.
    """
    raw = dsn.strip()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("postgresql", "postgres"):
        raise ValueError(
            f"DATABASE_URL must use postgresql:// or postgres://, got scheme {scheme!r}"
        )

    user = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password is not None else ""
    host = parsed.hostname
    if not host or not user:
        raise ValueError("DATABASE_URL must include a host and user (e.g. postgres.<ref>)")

    port = parsed.port or 5432
    database = (parsed.path or "").removeprefix("/").strip() or "postgres"

    qs = parse_qs(parsed.query)
    sslmode = (qs.get("sslmode", [""])[0] or "").lower()

    kwargs: Dict[str, Any] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }

    # libpq sslmode: "require" encrypts but does NOT verify server cert.
    # Only verify-ca / verify-full perform CA (and hostname) checks.
    use_ssl: Optional[bool] = None
    verify_peer: bool = False
    if sslmode == "disable":
        use_ssl = False
    elif sslmode in ("verify-ca", "verify-full"):
        use_ssl = True
        verify_peer = True
    elif sslmode in ("require", "prefer", "allow"):
        use_ssl = True
        verify_peer = False
    elif "supabase" in host.lower():
        use_ssl = True
        verify_peer = False

    if use_ssl is True:
        kwargs["ssl"] = (
            _postgres_ssl_context_verify() if verify_peer else _postgres_ssl_context_require()
        )
    elif use_ssl is False:
        kwargs["ssl"] = False

    return kwargs


class Database:
    """SQLite (default) or PostgreSQL when ``DATABASE_URL`` is set."""

    _sqlite: Optional[aiosqlite.Connection] = None
    _pg = None  # asyncpg.Pool, typed lazily

    @staticmethod
    def _use_postgres() -> bool:
        return bool(settings.database_url and settings.database_url.strip())

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @classmethod
    async def init(cls) -> None:
        if cls._use_postgres():
            import asyncpg

            try:
                pool_kwargs = _asyncpg_pool_kwargs(settings.database_url.strip())
            except ValueError as exc:
                log.error("Invalid DATABASE_URL: %s", exc)
                raise

            try:
                cls._pg = await asyncpg.create_pool(
                    min_size=1,
                    max_size=10,
                    **pool_kwargs,
                )
            except asyncpg.exceptions.InvalidPasswordError:
                log.error(
                    "PostgreSQL password rejected — copy the DB password from "
                    "Supabase → Project Settings → Database (not API keys). "
                    "Pooler user must be postgres.<project_ref>. "
                    "If the password has @ # / etc., percent-encode it in the URL "
                    "or reset the DB password to a simpler string and update Render."
                )
                raise
            async with cls._pg.acquire() as conn:
                for stmt in _PG_DDL:
                    await conn.execute(stmt)
            cls._sqlite = None
            log.info("PostgreSQL ready (DATABASE_URL)")
            return

        cls._sqlite = await aiosqlite.connect(settings.db_path, check_same_thread=False)
        cls._sqlite.row_factory = aiosqlite.Row
        await cls._sqlite.executescript(_SQLITE_SCHEMA)
        await cls._sqlite.commit()
        log.info("SQLite ready — %s", settings.db_path)

    @classmethod
    async def close(cls) -> None:
        if cls._pg is not None:
            await cls._pg.close()
            cls._pg = None
        if cls._sqlite is not None:
            await cls._sqlite.close()
            cls._sqlite = None

    # ── Messages ───────────────────────────────────────────────────────────

    @classmethod
    async def add_message(cls, role: str, content: str) -> None:
        tokens_est = len(content) // 4
        ts = _now_iso() if not cls._use_postgres() else _now_utc()
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                await conn.execute(
                    "INSERT INTO messages (role, content, tokens_est, created_at) "
                    "VALUES ($1, $2, $3, $4)",
                    role,
                    content,
                    tokens_est,
                    ts,
                )
            return
        await cls._sqlite.execute(
            "INSERT INTO messages (role, content, tokens_est, created_at) VALUES (?,?,?,?)",
            (role, content, tokens_est, ts if isinstance(ts, str) else ts.isoformat()),
        )
        await cls._sqlite.commit()

    @classmethod
    async def get_recent_history(cls, limit: int = 20) -> List[Dict]:
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT role, content FROM messages ORDER BY id DESC LIMIT $1",
                    limit,
                )
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        cur = await cls._sqlite.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    @classmethod
    async def get_message_count(cls) -> int:
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) AS c FROM messages")
            return int(row["c"])
        cur = await cls._sqlite.execute("SELECT COUNT(*) AS c FROM messages")
        row = await cur.fetchone()
        return row["c"]

    @classmethod
    async def clear_history(cls) -> None:
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                await conn.execute("DELETE FROM messages")
            return
        await cls._sqlite.execute("DELETE FROM messages")
        await cls._sqlite.commit()

    # ── Facts ──────────────────────────────────────────────────────────────

    @classmethod
    async def add_fact(cls, content: str, source: str = "extracted") -> bool:
        content = content.strip()
        ts = _now_iso() if not cls._use_postgres() else _now_utc()
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                row = await conn.fetchrow(
                    "INSERT INTO facts (content, source, created_at) VALUES ($1, $2, $3) "
                    "ON CONFLICT (content) DO NOTHING RETURNING id",
                    content,
                    source,
                    ts,
                )
            return row is not None
        try:
            await cls._sqlite.execute(
                "INSERT OR IGNORE INTO facts (content, source, created_at) VALUES (?,?,?)",
                (content, source, ts if isinstance(ts, str) else ts.isoformat()),
            )
            await cls._sqlite.commit()
            cur = await cls._sqlite.execute("SELECT changes() AS c")
            row = await cur.fetchone()
            return row["c"] > 0
        except Exception as exc:
            log.error("add_fact error: %s", exc)
            return False

    @classmethod
    async def get_all_facts(cls) -> List[str]:
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT content FROM facts ORDER BY created_at DESC"
                )
            return [r["content"] for r in rows]
        cur = await cls._sqlite.execute(
            "SELECT content FROM facts ORDER BY created_at DESC"
        )
        rows = await cur.fetchall()
        return [r["content"] for r in rows]

    @classmethod
    async def delete_facts_by_keyword(cls, keyword: str) -> int:
        pat = f"%{keyword}%"
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                rows = await conn.fetch(
                    "DELETE FROM facts WHERE content LIKE $1 RETURNING id", pat
                )
            return len(rows)
        cur = await cls._sqlite.execute(
            "DELETE FROM facts WHERE content LIKE ?", (pat,)
        )
        await cls._sqlite.commit()
        return cur.rowcount

    # ── KV stats ───────────────────────────────────────────────────────────

    @classmethod
    async def get_stat(cls, key: str, default: str = "0") -> str:
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value FROM kv_stats WHERE key = $1", key
                )
            return row["value"] if row else default
        cur = await cls._sqlite.execute(
            "SELECT value FROM kv_stats WHERE key=?", (key,)
        )
        row = await cur.fetchone()
        return row["value"] if row else default

    @classmethod
    async def set_stat(cls, key: str, value: str) -> None:
        if cls._pg is not None:
            async with cls._pg.acquire() as conn:
                await conn.execute(
                    "INSERT INTO kv_stats (key, value) VALUES ($1, $2) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    key,
                    value,
                )
            return
        await cls._sqlite.execute(
            "INSERT OR REPLACE INTO kv_stats (key, value) VALUES (?,?)", (key, value)
        )
        await cls._sqlite.commit()

    @classmethod
    async def increment_stat(cls, key: str, by: int = 1) -> int:
        val = int(await cls.get_stat(key, "0")) + by
        await cls.set_stat(key, str(val))
        return val
