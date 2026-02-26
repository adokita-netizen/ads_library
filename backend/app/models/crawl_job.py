"""Crawl job progress tracking model."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CrawlJobStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlJob(Base):
    """Tracks crawl job progress for real-time UI updates."""

    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[CrawlJobStatusEnum] = mapped_column(
        Enum(CrawlJobStatusEnum), default=CrawlJobStatusEnum.PENDING, nullable=False
    )

    # Query info
    query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    platforms: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Progress tracking
    total_platforms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_platforms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_ads_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
