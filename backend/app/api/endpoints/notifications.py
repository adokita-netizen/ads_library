"""Notification management API endpoints."""

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import SyncSessionLocal
from app.models.ad_metrics import NotificationConfig, SavedItem

logger = structlog.get_logger()
router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ==================== Schemas ====================


class NotificationConfigRequest(BaseModel):
    channel_type: str = Field(..., description="slack, chatwork, email")
    webhook_url: Optional[str] = None
    api_token: Optional[str] = None
    room_id: Optional[str] = None
    notify_new_hit_ads: bool = True
    notify_competitor_activity: bool = True
    notify_ranking_change: bool = False
    notify_fatigue_warning: bool = False
    watched_genres: Optional[list[str]] = None
    watched_advertisers: Optional[list[str]] = None


class NotificationConfigResponse(BaseModel):
    id: int
    channel_type: str
    webhook_url: Optional[str] = None
    room_id: Optional[str] = None
    notify_new_hit_ads: bool
    notify_competitor_activity: bool
    notify_ranking_change: bool
    notify_fatigue_warning: bool
    watched_genres: Optional[list[str]] = None
    watched_advertisers: Optional[list[str]] = None
    is_active: bool

    model_config = {"from_attributes": True}


class SavedItemRequest(BaseModel):
    item_type: str = Field(..., description="ad, lp, creative, advertiser")
    item_id: int
    label: Optional[str] = None
    notes: Optional[str] = None
    folder: Optional[str] = None


class SavedItemResponse(BaseModel):
    id: int
    item_type: str
    item_id: int
    label: Optional[str] = None
    notes: Optional[str] = None
    folder: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


# ==================== Notification Config ====================


@router.post("/config", response_model=NotificationConfigResponse)
async def create_notification_config(request: NotificationConfigRequest):
    """Create or update notification configuration."""
    # TODO: get user_id from auth token
    user_id = 1

    session = SyncSessionLocal()
    try:
        # Check existing config for this channel
        existing = session.query(NotificationConfig).filter(
            NotificationConfig.user_id == user_id,
            NotificationConfig.channel_type == request.channel_type,
        ).first()

        if existing:
            existing.webhook_url = request.webhook_url
            existing.api_token = request.api_token
            existing.room_id = request.room_id
            existing.notify_new_hit_ads = request.notify_new_hit_ads
            existing.notify_competitor_activity = request.notify_competitor_activity
            existing.notify_ranking_change = request.notify_ranking_change
            existing.notify_fatigue_warning = request.notify_fatigue_warning
            existing.watched_genres = request.watched_genres
            existing.watched_advertisers = request.watched_advertisers
            config = existing
        else:
            config = NotificationConfig(
                user_id=user_id,
                channel_type=request.channel_type,
                webhook_url=request.webhook_url,
                api_token=request.api_token,
                room_id=request.room_id,
                notify_new_hit_ads=request.notify_new_hit_ads,
                notify_competitor_activity=request.notify_competitor_activity,
                notify_ranking_change=request.notify_ranking_change,
                notify_fatigue_warning=request.notify_fatigue_warning,
                watched_genres=request.watched_genres,
                watched_advertisers=request.watched_advertisers,
            )
            session.add(config)

        session.commit()
        session.refresh(config)
        return NotificationConfigResponse.model_validate(config)
    finally:
        session.close()


@router.get("/config")
async def list_notification_configs():
    """List all notification configurations for current user."""
    user_id = 1  # TODO: from auth
    session = SyncSessionLocal()
    try:
        configs = session.query(NotificationConfig).filter(
            NotificationConfig.user_id == user_id,
        ).all()
        return {
            "configs": [NotificationConfigResponse.model_validate(c) for c in configs]
        }
    finally:
        session.close()


@router.delete("/config/{config_id}")
async def delete_notification_config(config_id: int):
    """Delete a notification configuration."""
    session = SyncSessionLocal()
    try:
        config = session.query(NotificationConfig).filter(
            NotificationConfig.id == config_id,
        ).first()
        if not config:
            raise HTTPException(status_code=404, detail="通知設定が見つかりません")

        session.delete(config)
        session.commit()
        return {"message": "通知設定を削除しました"}
    finally:
        session.close()


@router.post("/test")
async def test_notification(config_id: int):
    """Send a test notification."""
    session = SyncSessionLocal()
    try:
        config = session.query(NotificationConfig).filter(
            NotificationConfig.id == config_id,
        ).first()
        if not config:
            raise HTTPException(status_code=404, detail="通知設定が見つかりません")

        from app.services.notification.notification_service import NotificationService
        svc = NotificationService()

        test_data = [
            {"product_name": "テスト商品", "genre": "テスト", "view_increase": 10000, "spend_increase": 50000}
        ]

        import asyncio
        success = await svc.notify_hit_ads(config, test_data)
        return {"success": success, "message": "テスト通知を送信しました" if success else "通知の送信に失敗しました"}
    finally:
        session.close()


# ==================== Saved Items (マイリスト) ====================


@router.post("/saved", response_model=SavedItemResponse)
async def save_item(request: SavedItemRequest):
    """Save an item to My List (マイリスト)."""
    user_id = 1  # TODO: from auth
    session = SyncSessionLocal()
    try:
        # Check if already saved
        existing = session.query(SavedItem).filter(
            SavedItem.user_id == user_id,
            SavedItem.item_type == request.item_type,
            SavedItem.item_id == request.item_id,
        ).first()

        if existing:
            existing.label = request.label or existing.label
            existing.notes = request.notes or existing.notes
            existing.folder = request.folder or existing.folder
            item = existing
        else:
            item = SavedItem(
                user_id=user_id,
                item_type=request.item_type,
                item_id=request.item_id,
                label=request.label,
                notes=request.notes,
                folder=request.folder,
            )
            session.add(item)

        session.commit()
        session.refresh(item)
        return SavedItemResponse(
            id=item.id,
            item_type=item.item_type,
            item_id=item.item_id,
            label=item.label,
            notes=item.notes,
            folder=item.folder,
            created_at=item.created_at.isoformat(),
        )
    finally:
        session.close()


@router.get("/saved")
async def list_saved_items(
    item_type: Optional[str] = None,
    folder: Optional[str] = None,
):
    """List saved items (マイリスト)."""
    user_id = 1  # TODO: from auth
    session = SyncSessionLocal()
    try:
        query = session.query(SavedItem).filter(SavedItem.user_id == user_id)
        if item_type:
            query = query.filter(SavedItem.item_type == item_type)
        if folder:
            query = query.filter(SavedItem.folder == folder)

        items = query.order_by(SavedItem.created_at.desc()).all()

        return {
            "items": [
                SavedItemResponse(
                    id=i.id,
                    item_type=i.item_type,
                    item_id=i.item_id,
                    label=i.label,
                    notes=i.notes,
                    folder=i.folder,
                    created_at=i.created_at.isoformat(),
                )
                for i in items
            ],
            "total": len(items),
        }
    finally:
        session.close()


@router.delete("/saved/{item_id}")
async def remove_saved_item(item_id: int):
    """Remove an item from My List."""
    session = SyncSessionLocal()
    try:
        item = session.query(SavedItem).filter(SavedItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="保存アイテムが見つかりません")

        session.delete(item)
        session.commit()
        return {"message": "マイリストから削除しました"}
    finally:
        session.close()
