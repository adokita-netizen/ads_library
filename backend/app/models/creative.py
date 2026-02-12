"""Creative generation models."""

import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CreativeTypeEnum(str, enum.Enum):
    VIDEO_SCRIPT = "video_script"
    STORYBOARD = "storyboard"
    AD_COPY = "ad_copy"
    BANNER = "banner"
    LP_COPY = "lp_copy"
    NARRATION = "narration"


class GeneratedCreative(Base):
    __tablename__ = "generated_creatives"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    creative_type: Mapped[CreativeTypeEnum] = mapped_column(Enum(CreativeTypeEnum), nullable=False)

    # Input parameters
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    appeal_axis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_ad_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ads.id"), nullable=True)
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Generated output
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_structured: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Generation metadata
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Variation tracking
    variation_group_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    variation_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class CreativeTemplate(Base):
    __tablename__ = "creative_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    creative_type: Mapped[CreativeTypeEnum] = mapped_column(Enum(CreativeTypeEnum), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    winning_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
