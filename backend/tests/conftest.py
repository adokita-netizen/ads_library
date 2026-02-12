"""Shared test fixtures for the VAAP backend test suite."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Override settings BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["DATABASE_URL_SYNC"] = "sqlite://"
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/15"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/15"

# Patch app.core.database BEFORE it gets imported by models
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.compiler import compiles


# Make JSONB compile as JSON for SQLite
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Make BigInteger compile as INTEGER for SQLite (enables autoincrement)
_orig_visit_BIGINT = SQLiteTypeCompiler.visit_BIGINT
SQLiteTypeCompiler.visit_BIGINT = lambda self, type_, **kw: "INTEGER"


class Base(DeclarativeBase):
    pass


_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create a mock database module and inject it BEFORE any app imports
# This prevents the real database.py from creating PostgreSQL engines
import types
db_mock = types.ModuleType("app.core.database")
db_mock.__package__ = "app.core"
db_mock.Base = Base
db_mock.sync_engine = _test_engine
db_mock.SyncSessionLocal = sessionmaker(bind=_test_engine, expire_on_commit=False)
db_mock.async_engine = MagicMock()
db_mock.AsyncSessionLocal = MagicMock()
db_mock.get_async_session = MagicMock()
db_mock.get_sync_session = MagicMock()

sys.modules["app.core.database"] = db_mock

# Now we can safely import models
import pytest  # noqa: E402

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum  # noqa: E402

# Import all model modules to register tables on Base
import app.models.competitive_intel  # noqa: E402, F401
import app.models.analysis  # noqa: E402, F401
import app.models.campaign  # noqa: E402, F401
import app.models.ad_metrics  # noqa: E402, F401
import app.models.landing_page  # noqa: E402, F401
import app.models.user  # noqa: E402, F401

# Create all tables
Base.metadata.create_all(bind=_test_engine)


@pytest.fixture(scope="session")
def engine():
    """Return the shared test engine."""
    yield _test_engine


@pytest.fixture
def session(engine):
    """Create a test database session with cleanup after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, expire_on_commit=False)
    sess = TestSession()

    yield sess

    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_ad(session) -> Ad:
    """Create a sample ad for testing."""
    ad = Ad(
        external_id="test_ad_001",
        title="テスト美容広告",
        description="テスト用の美容広告です",
        platform=AdPlatformEnum.YOUTUBE,
        status=AdStatusEnum.ANALYZED,
        advertiser_name="テスト美容株式会社",
        brand_name="テストブランド",
        video_url="https://example.com/video.mp4",
        duration_seconds=30.0,
        view_count=100000,
        like_count=5000,
        first_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ad_metadata={"genre": "美容・コスメ"},
        tags=["美容", "コスメ"],
    )
    session.add(ad)
    session.flush()
    return ad


@pytest.fixture
def sample_ads(session) -> list[Ad]:
    """Create multiple sample ads across different platforms."""
    ads = []
    platforms = [
        (AdPlatformEnum.YOUTUBE, "YouTube Ad", "yt_001"),
        (AdPlatformEnum.TIKTOK, "TikTok Ad", "tt_001"),
        (AdPlatformEnum.FACEBOOK, "Facebook Ad", "fb_001"),
        (AdPlatformEnum.INSTAGRAM, "Instagram Ad", "ig_001"),
        (AdPlatformEnum.YAHOO, "Yahoo Ad", "yh_001"),
        (AdPlatformEnum.X_TWITTER, "X Ad", "xt_001"),
        (AdPlatformEnum.LINE, "LINE Ad", "ln_001"),
        (AdPlatformEnum.PINTEREST, "Pinterest Ad", "pin_001"),
        (AdPlatformEnum.SMARTNEWS, "SmartNews Ad", "sn_001"),
        (AdPlatformEnum.GOOGLE_ADS, "Google Ad", "gads_001"),
        (AdPlatformEnum.GUNOSY, "Gunosy Ad", "gn_001"),
    ]

    for platform, title, ext_id in platforms:
        ad = Ad(
            external_id=ext_id,
            title=title,
            platform=platform,
            status=AdStatusEnum.PENDING,
            advertiser_name=f"{title} Advertiser",
            view_count=50000,
        )
        session.add(ad)
        ads.append(ad)

    session.flush()
    return ads
