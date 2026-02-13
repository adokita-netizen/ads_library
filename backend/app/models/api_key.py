"""Platform API key storage model."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlatformAPIKey(Base):
    """Stores API keys/tokens for each ad platform.

    Keys are stored per platform+key_name combination.
    For platforms with a single key, key_name = 'default'.
    For platforms with multiple keys (e.g. Google Ads), each credential
    has its own key_name (developer_token, client_id, client_secret, refresh_token).
    """

    __tablename__ = "platform_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key_name: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    key_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    def __repr__(self) -> str:
        return f"<PlatformAPIKey(platform={self.platform}, key_name={self.key_name})>"
