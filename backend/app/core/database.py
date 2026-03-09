"""Database connection and session management.

Supports PostgreSQL with automatic fallback to
in-memory SQLite when the configured database is unreachable.
"""

import os
import logging
import time
from functools import wraps

from sqlalchemy import BigInteger, create_engine, event, text
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Always patch BigInteger for SQLite compatibility ─────────────
# SQLite only auto-increments INTEGER PRIMARY KEY (not BIGINT).
# Apply this unconditionally so SQLite URLs in DATABASE_URL work.
from sqlalchemy.dialects.sqlite import base as _sqlite_base

def _visit_bigint_as_integer(self, type_, **kw):
    return "INTEGER"

_sqlite_base.SQLiteTypeCompiler.visit_BIGINT = _visit_bigint_as_integer

# ── State ────────────────────────────────────────────────────────
_in_memory_mode = False
_connection_error: str | None = None

# ── Job reentry lock ─────────────────────────────────────────────
_job_locks: dict[str, float] = {}
_JOB_LOCK_TTL = 600  # 10 minutes default


def acquire_job_lock(job_name: str, ttl: int = _JOB_LOCK_TTL) -> bool:
    """Acquire a process-level lock for a named job.

    Prevents the same job from running concurrently within this process.
    Returns True if lock acquired, False if already running.
    Stale locks (older than ttl seconds) are automatically released.
    """
    now = time.time()
    if job_name in _job_locks:
        elapsed = now - _job_locks[job_name]
        if elapsed < ttl:
            logger.warning("job_lock_denied job=%s held_for_seconds=%d", job_name, round(elapsed))
            return False
        logger.info("job_lock_stale_released job=%s held_for_seconds=%d", job_name, round(elapsed))
    _job_locks[job_name] = now
    return True


def release_job_lock(job_name: str):
    """Release a previously acquired job lock."""
    _job_locks.pop(job_name, None)


def job_locked(job_name: str, ttl: int = _JOB_LOCK_TTL):
    """Decorator: wrap a function with acquire/release job lock.

    If the lock cannot be acquired, the function is skipped and returns
    {"status": "skipped", "reason": "already_running"}.

    Usage:
        @job_locked("my_batch_job", ttl=600)
        def run_batch():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not acquire_job_lock(job_name, ttl=ttl):
                logger.warning("job_locked_skipped", job=job_name, function=fn.__name__)
                return {"status": "skipped", "reason": "already_running"}
            try:
                return fn(*args, **kwargs)
            finally:
                release_job_lock(job_name)
        return wrapper
    return decorator


def is_in_memory_mode() -> bool:
    return _in_memory_mode


def get_connection_error() -> str | None:
    return _connection_error


# ── Retry utilities ──────────────────────────────────────────────

_DB_RETRY_MAX = 3
_DB_RETRY_BASE_DELAY = 1.0  # seconds
_DB_RETRY_MAX_DELAY = 10.0  # seconds


def _exponential_backoff(attempt: int) -> float:
    """Calculate delay with exponential backoff: 1s, 2s, 4s... capped at max."""
    delay = min(_DB_RETRY_BASE_DELAY * (2 ** attempt), _DB_RETRY_MAX_DELAY)
    return delay


def db_retry(func=None, *, max_retries=_DB_RETRY_MAX):
    """Decorator: retry DB operations on transient connection errors.

    Applies exponential backoff (1s, 2s, 4s...).
    After max_retries, raises the original exception with structured log.

    Usage:
        @db_retry
        def my_db_function():
            with sync_session_scope() as session:
                ...

        @db_retry(max_retries=5)
        def another_function():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except (OperationalError, DBAPIError, ConnectionError, OSError) as e:
                    last_exc = e
                    if attempt >= max_retries:
                        logger.error(
                            "db_retry_exhausted",
                            function=fn.__name__,
                            attempts=attempt + 1,
                            error=str(e),
                        )
                        raise
                    delay = _exponential_backoff(attempt)
                    logger.warning(
                        "db_retry_attempt",
                        function=fn.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=delay,
                        error=str(e),
                    )
                    time.sleep(delay)
            raise last_exc  # should not reach here
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


# ── Engine creation with fallback ────────────────────────────────

def _try_create_engines(async_url: str, sync_url: str):
    """Try to connect to the database. Returns (async_engine, sync_engine) or raises."""
    _is_sqlite = "sqlite" in sync_url.lower()
    _is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

    if _is_sqlite:
        # SQLite: use NullPool (no connection pooling) and check_same_thread=False
        # pool_size / max_overflow are not compatible with NullPool / StaticPool.
        from sqlalchemy.pool import StaticPool

        sqlite_connect_args = {"check_same_thread": False}

        ae = create_async_engine(
            async_url,
            echo=settings.debug,
            hide_parameters=True,
            connect_args=sqlite_connect_args,
            poolclass=StaticPool,
        )
        se = create_engine(
            sync_url,
            echo=settings.debug,
            hide_parameters=True,
            connect_args=sqlite_connect_args,
            poolclass=StaticPool,
        )

        # Enable WAL journal mode for better concurrency
        @event.listens_for(se, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    else:
        # PostgreSQL: connection pool + timeouts
        # CI-077: Standard timeouts (ms) — prevent runaway queries and lock waits
        _STATEMENT_TIMEOUT = "30000" if _is_lambda else "60000"  # 30s Lambda / 60s container
        _LOCK_TIMEOUT = "10000"  # 10s for all environments

        if _is_lambda:
            pool_kwargs = {
                "pool_size": 2,
                "max_overflow": 1,
                "pool_recycle": 300,
                "pool_timeout": 10,
            }
        else:
            pool_kwargs = {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_recycle": 300,
            }

        connect_args = {
            "connect_timeout": 5,
            "options": f"-c statement_timeout={_STATEMENT_TIMEOUT} -c lock_timeout={_LOCK_TIMEOUT}",
        }

        ae = create_async_engine(
            async_url,
            echo=settings.debug,
            hide_parameters=True,
            pool_pre_ping=True,
            **pool_kwargs,
        )
        se = create_engine(
            sync_url,
            echo=settings.debug,
            hide_parameters=True,
            pool_pre_ping=True,
            connect_args=connect_args,
            **pool_kwargs,
        )

    # Quick connection test (sync)
    with se.connect() as conn:
        conn.execute(text("SELECT 1"))
    return ae, se


def _create_sqlite_engines():
    """Create in-memory SQLite engines as fallback."""
    se = create_engine("sqlite:///vaap_fallback.db", echo=settings.debug, hide_parameters=True)
    # For async we use aiosqlite
    ae = create_async_engine("sqlite+aiosqlite:///vaap_fallback.db", echo=settings.debug, hide_parameters=True)

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
        msg += "DATABASE_URLのパスワードを確認してください。"
        return msg
    if "could not connect" in err_str or "connection refused" in err_str:
        return "接続エラー: データベースサーバーに接続できません。DATABASE_URLを確認してください。"
    if "does not exist" in err_str:
        return "接続エラー: データベースが存在しません。データベースが存在するか確認してください。"
    if "timeout" in err_str:
        return "接続エラー: データベースサーバーへの接続がタイムアウトしました。"
    return f"接続エラー: {str(error)}"


# ── Initialize engines ───────────────────────────────────────────

_is_default_url = (
    settings.database_url == "postgresql+asyncpg://vaap:vaap_password@localhost:5432/vaap_db"
    or "localhost" in settings.database_url
)

def _connect_with_retry():
    """Attempt PostgreSQL connection with exponential backoff before falling back to SQLite."""
    global _in_memory_mode, _connection_error
    last_error = None
    for attempt in range(_DB_RETRY_MAX + 1):
        try:
            ae, se = _try_create_engines(settings.database_url, settings.database_url_sync)
            if attempt > 0:
                logger.info("db_connect_recovered after %d attempts", attempt + 1)
            _db_type = "SQLite" if "sqlite" in settings.database_url.lower() else "PostgreSQL"
            logger.info("%s connected: %s", _db_type, settings.database_url.split("@")[-1] if "@" in settings.database_url else "(local)")
            return ae, se
        except Exception as e:
            last_error = e
            if attempt < _DB_RETRY_MAX:
                delay = _exponential_backoff(attempt)
                logger.warning(
                    "db_connect_retry attempt=%d/%d delay=%.1fs error=%s",
                    attempt + 1, _DB_RETRY_MAX, delay, str(e),
                )
                time.sleep(delay)

    # All retries exhausted — fall back to SQLite
    _connection_error = _diagnose_error(last_error, settings.database_url)
    if _is_default_url:
        logger.info("No PostgreSQL configured, using in-memory SQLite fallback.")
    else:
        logger.error(
            "db_connect_failed after %d attempts: %s",
            _DB_RETRY_MAX + 1, _connection_error,
        )
        logger.warning("PostgreSQL connection failed: %s — falling back to SQLite", _connection_error)
    _in_memory_mode = True
    return _create_sqlite_engines()


async_engine, sync_engine = _connect_with_retry()


# ── Pool health monitoring (CI-107) ──────────────────────────────

_POOL_WARN_THRESHOLD = 0.8  # warn when 80% of pool is in use


def check_pool_health() -> dict:
    """Return pool utilization stats. Logs warning if near exhaustion."""
    try:
        pool = sync_engine.pool
        size = pool.size()
        checked_out = pool.checkedout()
        overflow = pool.overflow()
        max_overflow = sync_engine.pool._max_overflow

        utilization = checked_out / max(size, 1)
        total_capacity = size + max_overflow
        total_in_use = checked_out + max(overflow, 0)

        stats = {
            "pool_size": size,
            "checked_out": checked_out,
            "checked_in": pool.checkedin(),
            "overflow": overflow,
            "max_overflow": max_overflow,
            "utilization": round(utilization, 2),
            "total_capacity": total_capacity,
            "total_in_use": total_in_use,
        }

        if total_capacity > 0 and total_in_use / total_capacity >= _POOL_WARN_THRESHOLD:
            logger.warning(
                "db_pool_near_exhaustion utilization=%.0f%% in_use=%d/%d",
                total_in_use / total_capacity * 100, total_in_use, total_capacity,
            )
            stats["warning"] = "near_exhaustion"

        return stats
    except Exception as e:
        return {"error": str(e)}


# Attach checkout listener for pool exhaustion early warning
if not _in_memory_mode:
    @event.listens_for(sync_engine, "checkout")
    def _on_checkout(dbapi_conn, connection_record, connection_proxy):
        try:
            pool = sync_engine.pool
            size = pool.size()
            checked_out = pool.checkedout()
            max_overflow = pool._max_overflow
            total_capacity = size + max_overflow
            if total_capacity > 0 and checked_out / total_capacity >= _POOL_WARN_THRESHOLD:
                logger.warning(
                    "db_pool_checkout_warning checked_out=%d capacity=%d",
                    checked_out, total_capacity,
                )
        except Exception:
            pass


# Session factories (primary — read/write)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)


# ── Read Replica (CI-137) ────────────────────────────────────────
# If DATABASE_READ_URL is set, create separate read-only engines.
# Otherwise, read sessions transparently use the primary engine.

_read_replica_enabled = False

if settings.database_read_url and not _in_memory_mode:
    try:
        _read_async_engine, _read_sync_engine = _try_create_engines(
            settings.database_read_url, settings.database_read_url_sync,
        )
        _read_replica_enabled = True
        logger.info(
            "Read replica connected: %s",
            settings.database_read_url.split("@")[-1] if "@" in settings.database_read_url else "(read)",
        )
    except Exception as e:
        logger.warning("Read replica connection failed, using primary for reads: %s", e)
        _read_async_engine = async_engine
        _read_sync_engine = sync_engine
else:
    _read_async_engine = async_engine
    _read_sync_engine = sync_engine

AsyncReadSession = async_sessionmaker(
    bind=_read_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SyncReadSession = sessionmaker(
    bind=_read_sync_engine,
    expire_on_commit=False,
)


def is_read_replica_enabled() -> bool:
    """Check if a separate read replica is active."""
    return _read_replica_enabled


class Base(DeclarativeBase):
    pass


def get_session_with_retry(max_retries: int = _DB_RETRY_MAX, base_delay: float = _DB_RETRY_BASE_DELAY):
    """Get a sync session with connection-test retry and exponential backoff.

    Useful for batch scripts and Lambda cold-starts where the first
    connection attempt may fail due to RDS wake-up or network jitter.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            session = SyncSessionLocal()
            session.execute(text("SELECT 1"))
            return session
        except (OperationalError, DBAPIError, ConnectionError, OSError) as e:
            last_error = e
            if attempt >= max_retries:
                logger.error(
                    "get_session_with_retry exhausted attempts=%d error=%s",
                    attempt + 1, str(e),
                )
                raise
            delay = _exponential_backoff(attempt)
            logger.warning(
                "get_session_with_retry attempt=%d/%d delay=%.1fs error=%s",
                attempt + 1, max_retries, delay, str(e),
            )
            time.sleep(delay)
    raise last_error  # unreachable


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
    session = get_session_with_retry()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_async_read_session() -> AsyncSession:
    """Async read-only session (uses replica if configured, else primary)."""
    async with AsyncReadSession() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_read_session():
    """Sync read-only session (uses replica if configured, else primary)."""
    session = SyncReadSession()
    try:
        yield session
    finally:
        session.close()


from contextlib import contextmanager  # noqa: E402


def _run_migrations(engine):
    """Add missing columns to existing tables (lightweight auto-migration)."""
    from sqlalchemy import inspect as sa_inspect, text as sa_text
    try:
        insp = sa_inspect(engine)
        # landing_pages: add error_message
        if insp.has_table("landing_pages"):
            cols = {c["name"] for c in insp.get_columns("landing_pages")}
            if "error_message" not in cols:
                with engine.begin() as conn:
                    conn.execute(sa_text("ALTER TABLE landing_pages ADD COLUMN error_message TEXT"))
                    logger.info("migration: added landing_pages.error_message")

        # ads: add new columns for thumbnail, destination, and operational metrics
        if insp.has_table("ads"):
            cols = {c["name"] for c in insp.get_columns("ads")}
            new_cols = {
                "thumbnail_url": "TEXT",
                "destination_url": "TEXT",
                "spend": "FLOAT",
                "impressions": "BIGINT",
                "reach": "BIGINT",
                "cpc": "FLOAT",
                "cpm": "FLOAT",
                "frequency": "FLOAT",
            }
            with engine.begin() as conn:
                for col_name, col_type in new_cols.items():
                    if col_name not in cols:
                        conn.execute(sa_text(f"ALTER TABLE ads ADD COLUMN {col_name} {col_type}"))
                        logger.info("migration: added ads.%s", col_name)

        # crawl_jobs: add columns that may be missing from earlier schema
        if insp.has_table("crawl_jobs"):
            cols = {c["name"] for c in insp.get_columns("crawl_jobs")}
            cj_new_cols = {
                "failure_reason": "VARCHAR(50)",
                "progress_detail": "JSON",
            }
            with engine.begin() as conn:
                for col_name, col_type in cj_new_cols.items():
                    if col_name not in cols:
                        conn.execute(sa_text(f"ALTER TABLE crawl_jobs ADD COLUMN {col_name} {col_type}"))
                        logger.info("migration: added crawl_jobs.%s", col_name)

        # product_rankings: add score/trend columns introduced after initial local DBs
        if insp.has_table("product_rankings"):
            cols = {c["name"] for c in insp.get_columns("product_rankings")}
            pr_new_cols = {
                "score_delta": "FLOAT",
                "trend_score": "FLOAT",
            }
            with engine.begin() as conn:
                for col_name, col_type in pr_new_cols.items():
                    if col_name not in cols:
                        conn.execute(sa_text(f"ALTER TABLE product_rankings ADD COLUMN {col_name} {col_type}"))
                        logger.info("migration: added product_rankings.%s", col_name)
    except Exception as e:
        logger.warning("migration_check_failed: %s", str(e))


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
        import app.models.crawl_job  # noqa: F401
        import app.models.alert_rule  # noqa: F401
        import app.models.alert_history  # noqa: F401
        import app.models.conversation  # noqa: F401
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
