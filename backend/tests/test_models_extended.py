"""Extended model tests — User model, Ad querying, and edge cases."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.user import User, UserRole


class TestUserModel:
    """Test User ORM model."""

    def test_create_user(self, session: Session):
        user = User(
            email="test@example.com",
            hashed_password="$2b$12$fakehashvalue",
            full_name="テストユーザー",
            role=UserRole.VIEWER,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.is_active is True

    def test_user_default_role(self, session: Session):
        user = User(
            email="default@example.com",
            hashed_password="hash",
            full_name="Default User",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.role == UserRole.VIEWER

    def test_user_admin_role(self, session: Session):
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        session.add(user)
        session.commit()
        assert user.role == UserRole.ADMIN


class TestAdQueryPatterns:
    """Test common Ad query patterns used by API endpoints."""

    def test_filter_by_platform(self, sample_ads, session: Session):
        results = session.query(Ad).filter(
            Ad.platform == AdPlatformEnum.YOUTUBE
        ).all()
        assert len(results) >= 1
        assert all(ad.platform == AdPlatformEnum.YOUTUBE for ad in results)

    def test_filter_by_status(self, sample_ad, session: Session):
        results = session.query(Ad).filter(
            Ad.status == AdStatusEnum.ANALYZED
        ).all()
        assert len(results) >= 1

    def test_filter_by_advertiser_ilike(self, sample_ad, session: Session):
        results = session.query(Ad).filter(
            Ad.advertiser_name.ilike("%テスト%")
        ).all()
        assert len(results) >= 1

    def test_order_by_created_at(self, sample_ads, session: Session):
        results = session.query(Ad).order_by(Ad.created_at.desc()).all()
        assert len(results) >= 1

    def test_count_ads(self, sample_ads, session: Session):
        from sqlalchemy import func
        count = session.query(func.count(Ad.id)).scalar()
        assert count >= len(sample_ads)

    def test_pagination_offset_limit(self, sample_ads, session: Session):
        page_size = 3
        page1 = session.query(Ad).offset(0).limit(page_size).all()
        page2 = session.query(Ad).offset(page_size).limit(page_size).all()
        assert len(page1) == page_size
        assert len(page2) == page_size
        # Pages should have different items
        page1_ids = {ad.id for ad in page1}
        page2_ids = {ad.id for ad in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestAdStatusTransitions:
    """Test that ad status transitions work correctly."""

    def test_pending_to_processing(self, session: Session):
        ad = Ad(platform=AdPlatformEnum.YOUTUBE, status=AdStatusEnum.PENDING)
        session.add(ad)
        session.commit()

        ad.status = AdStatusEnum.PROCESSING
        session.commit()
        session.refresh(ad)
        assert ad.status == AdStatusEnum.PROCESSING

    def test_processing_to_analyzed(self, session: Session):
        ad = Ad(platform=AdPlatformEnum.TIKTOK, status=AdStatusEnum.PROCESSING)
        session.add(ad)
        session.commit()

        ad.status = AdStatusEnum.ANALYZED
        session.commit()
        session.refresh(ad)
        assert ad.status == AdStatusEnum.ANALYZED

    def test_processing_to_failed(self, session: Session):
        ad = Ad(platform=AdPlatformEnum.FACEBOOK, status=AdStatusEnum.PROCESSING)
        session.add(ad)
        session.commit()

        ad.status = AdStatusEnum.FAILED
        session.commit()
        session.refresh(ad)
        assert ad.status == AdStatusEnum.FAILED
