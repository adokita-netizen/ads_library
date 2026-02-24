"""Database connection and session management.

Supports PostgreSQL (Supabase/Render/etc.) with automatic fallback to
in-memory SQLite when the configured database is unreachable.
"""

import os
import logging

from sqlalchemy import BigInteger, create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── State ────────────────────────────────────────────────────────
_in_memory_mode = False
_connection_error: str | None = None


def is_in_memory_mode() -> bool:
    return _in_memory_mode


def get_connection_error() -> str | None:
    return _connection_error


# ── Engine creation with fallback ────────────────────────────────

def _try_create_engines(async_url: str, sync_url: str):
    """Try to connect to PostgreSQL. Returns (async_engine, sync_engine) or raises."""
    ae = create_async_engine(
        async_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,  # Recycle connections after 30 min (prevents stale connections)
    )
    se = create_engine(
        sync_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    # Quick connection test (sync)
    with se.connect() as conn:
        conn.execute(text("SELECT 1"))
    return ae, se


def _create_sqlite_engines():
    """Create in-memory SQLite engines as fallback."""
    se = create_engine("sqlite:///vaap_fallback.db", echo=settings.debug)
    # For async we use aiosqlite
    ae = create_async_engine("sqlite+aiosqlite:///vaap_fallback.db", echo=settings.debug)

    # Fix: SQLite only auto-increments INTEGER PRIMARY KEY (not BIGINT).
    # Compile BigInteger as INTEGER on SQLite so autoincrement works.
    from sqlalchemy.dialects import sqlite as sqlite_dialect

    @event.listens_for(se, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    # Register type adapter: BigInteger -> INTEGER for SQLite DDL
    from sqlalchemy.types import TypeDecorator

    class _SQLiteBigInteger(TypeDecorator):
        impl = BigInteger
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == "sqlite":
                return dialect.type_descriptor(BigInteger().adapt(BigInteger))
            return dialect.type_descriptor(BigInteger())

    # Monkey-patch BigInteger for SQLite: render as INTEGER
    from sqlalchemy.dialects.sqlite import base as sqlite_base
    _orig_visit = getattr(sqlite_base.SQLiteTypeCompiler, "visit_BIGINT", None)

    def _visit_bigint_as_integer(self, type_, **kw):
        return "INTEGER"

    sqlite_base.SQLiteTypeCompiler.visit_BIGINT = _visit_bigint_as_integer

    return ae, se


def _diagnose_error(error: Exception, url: str) -> str:
    """Generate a user-friendly error message in Japanese."""
    err_str = str(error).lower()
    if "password authentication failed" in err_str:
        msg = "接続エラー: パスワード認証に失敗しました。"
        if ":6543" in url or "pooler" in url.lower():
            msg += "Supabaseダッシュボードでパスワードを確認してください。Pooler (ポート6543) を使用する場合、ユーザー名は 'postgres.{project-ref}' 形式が必要です。"
        else:
            msg += "Supabaseダッシュボードでパスワードを確認してください。"
        return msg
    if "could not connect" in err_str or "connection refused" in err_str:
        return "接続エラー: データベースサーバーに接続できません。DATABASE_URLを確認してください。"
    if "does not exist" in err_str:
        return "接続エラー: データベースが存在しません。Supabaseでプロジェクトが作成されているか確認してください。"
    if "timeout" in err_str:
        return "接続エラー: データベースサーバーへの接続がタイムアウトしました。"
    return f"接続エラー: {str(error)}"


# ── Initialize engines ───────────────────────────────────────────

_is_default_url = (
    settings.database_url == "postgresql+asyncpg://vaap:vaap_password@localhost:5432/vaap_db"
    or "localhost" in settings.database_url
)

try:
    async_engine, sync_engine = _try_create_engines(
        settings.database_url, settings.database_url_sync
    )
    logger.info("PostgreSQL connected: %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else "(local)")
except Exception as e:
    _connection_error = _diagnose_error(e, settings.database_url)
    if _is_default_url:
        logger.info("No PostgreSQL configured, using in-memory SQLite fallback.")
    else:
        logger.warning("PostgreSQL connection failed: %s — falling back to SQLite", _connection_error)
    async_engine, sync_engine = _create_sqlite_engines()
    _in_memory_mode = True


# Session factories
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


from contextlib import contextmanager  # noqa: E402


@contextmanager
def sync_session_scope():
    """Context manager for sync session with automatic rollback on error.

    Usage:
        with sync_session_scope() as session:
            session.query(...)
            session.commit()  # explicit commit when needed
    """
    session = SyncSessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Runtime reconnection ─────────────────────────────────────────

def reconnect(new_database_url: str) -> dict:
    """Attempt to connect to a new DATABASE_URL at runtime.

    Returns {"ok": True} on success, {"ok": False, "error": str} on failure.
    Also persists the URL to the .env file if successful.
    """
    global async_engine, sync_engine, AsyncSessionLocal, SyncSessionLocal
    global _in_memory_mode, _connection_error

    from app.core.config import _normalize_database_url

    async_url = _normalize_database_url(new_database_url, driver="asyncpg")
    sync_url = _normalize_database_url(new_database_url, driver="sync")

    try:
        new_async, new_sync = _try_create_engines(async_url, sync_url)
    except Exception as e:
        diag = _diagnose_error(e, new_database_url)
        return {"ok": False, "error": diag}

    # Success — swap engines
    async_engine = new_async
    sync_engine = new_sync
    AsyncSessionLocal.configure(bind=async_engine)
    SyncSessionLocal.configure(bind=sync_engine)
    _in_memory_mode = False
    _connection_error = None

    # Create tables on new database
    try:
        import app.models.ad  # noqa: F401
        import app.models.ad_metrics  # noqa: F401
        import app.models.analysis  # noqa: F401
        import app.models.user  # noqa: F401
        import app.models.landing_page  # noqa: F401
        import app.models.api_key  # noqa: F401
        Base.metadata.create_all(bind=sync_engine)
        logger.info("Tables created on new database.")
    except Exception as table_err:
        logger.warning("Table creation on new DB: %s", table_err)

    # Persist to .env
    _persist_env("DATABASE_URL", new_database_url)

    logger.info("Reconnected to PostgreSQL: %s", async_url.split("@")[-1] if "@" in async_url else "(url)")
    return {"ok": True}


def _persist_env(key: str, value: str):
    """Write or update a key in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    lines: list[str] = []
    found = False
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        pass

    new_line = f"{key}={value}\n"
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = new_line
            found = True
            break

    if not found:
        lines.append(new_line)

    with open(env_path, "w") as f:
        f.writelines(lines)
