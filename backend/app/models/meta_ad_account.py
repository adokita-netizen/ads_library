"""Meta Ad Account model — represents connected Meta advertising accounts."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MetaAdAccount(Base):
    """A Meta (Facebook/Instagram) ad account connected to the platform.

    Stores account metadata and sync status for campaign data synchronization.
    """

    __tablename__ = "meta_ad_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="JPY", nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(100), default="Asia/Tokyo", nullable=False)
    account_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Sync tracking
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Account metrics
    amount_spent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships (added in Phase 2)
    # campaigns = relationship("MetaCampaign", back_populates="account", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<MetaAdAccount(account_id={self.account_id}, name={self.account_name})>"
