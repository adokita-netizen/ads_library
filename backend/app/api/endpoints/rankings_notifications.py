"""C-R2-2 Notification and Alert Rule API under /rankings."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_sync
from app.core.database import sync_session_scope
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/rankings", tags=["Rankings Notifications"])


class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    condition_type: str = Field(..., min_length=1, max_length=50)
    target_field: Optional[str] = Field(default=None, max_length=100)
    operator: Optional[str] = Field(default=None, max_length=10)
    threshold: Optional[float] = None
    genre_filter: Optional[str] = Field(default=None, max_length=100)
    notification_channel: str = Field(default="in_app", max_length=50)
    cooldown_minutes: int = Field(default=60, ge=0, le=10080)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True
    metadata: Optional[dict] = None


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    condition_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    target_field: Optional[str] = Field(default=None, max_length=100)
    operator: Optional[str] = Field(default=None, max_length=10)
    threshold: Optional[float] = None
    genre_filter: Optional[str] = Field(default=None, max_length=100)
    notification_channel: Optional[str] = Field(default=None, max_length=50)
    cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=10080)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


def _to_notification_row(item: AlertHistory) -> dict:
    return {
        "id": item.id,
        "type": item.alert_type,
        "title": item.title,
        "body": item.message or "",
        "read": bool(item.is_read),
        "created_at": item.triggered_at.isoformat() if item.triggered_at else None,
        "ad_id": item.ad_id,
        "action_url": None,
        "severity": item.severity,
        "metadata": item.alert_metadata or {},
    }


@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    type_filter: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        query = session.query(AlertHistory)
        if unread_only:
            query = query.filter(AlertHistory.is_read.is_(False))
        if type_filter:
            query = query.filter(AlertHistory.alert_type == type_filter)

        total = query.count()
        rows = (
            query.order_by(AlertHistory.triggered_at.desc(), AlertHistory.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        unread_count = (
            session.query(AlertHistory)
            .filter(AlertHistory.is_read.is_(False))
            .count()
        )
        return {
            "notifications": [_to_notification_row(r) for r in rows],
            "unread_count": unread_count,
            "total": total,
            "page": page,
            "per_page": per_page,
        }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        row = session.query(AlertHistory).filter(AlertHistory.id == notification_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")
        if not row.is_read:
            row.is_read = True
            row.read_at = datetime.now(timezone.utc)
            session.commit()
        return {"id": row.id, "read": True, "read_at": row.read_at.isoformat() if row.read_at else None}


@router.put("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        svc = NotificationService(session)
        updated = svc.mark_all_as_read()
        return {"updated": updated}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        row = session.query(AlertHistory).filter(AlertHistory.id == notification_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")
        session.delete(row)
        session.commit()
        return {"deleted": True, "id": notification_id}


@router.post("/alert-rules")
async def create_alert_rule(
    body: AlertRuleCreate,
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        row = AlertRule(
            name=body.name,
            description=body.description,
            condition_type=body.condition_type,
            target_field=body.target_field,
            operator=body.operator,
            threshold=body.threshold,
            genre_filter=body.genre_filter,
            is_active=body.is_active,
            notification_channel=body.notification_channel,
            cooldown_minutes=body.cooldown_minutes,
            rule_metadata=body.metadata or {},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "name": row.name,
            "condition_type": row.condition_type,
            "target_field": row.target_field,
            "operator": row.operator,
            "threshold": row.threshold,
            "genre_filter": row.genre_filter,
            "notification_channel": row.notification_channel,
            "cooldown_minutes": row.cooldown_minutes,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "metadata": row.rule_metadata or {},
        }


@router.get("/alert-rules")
async def list_alert_rules(
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        rows = session.query(AlertRule).order_by(AlertRule.id.desc()).all()
        return {
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "condition_type": r.condition_type,
                    "target_field": r.target_field,
                    "operator": r.operator,
                    "threshold": r.threshold,
                    "genre_filter": r.genre_filter,
                    "notification_channel": r.notification_channel,
                    "cooldown_minutes": r.cooldown_minutes,
                    "is_active": r.is_active,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    "metadata": r.rule_metadata or {},
                }
                for r in rows
            ],
            "total": len(rows),
        }


@router.put("/alert-rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        row = session.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Alert rule not found")

        payload = body.model_dump(exclude_unset=True)
        if "metadata" in payload:
            payload["rule_metadata"] = payload.pop("metadata")
        for key, value in payload.items():
            setattr(row, key, value)

        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "name": row.name,
            "is_active": row.is_active,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    with sync_session_scope() as session:
        row = session.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        session.delete(row)
        session.commit()
        return {"deleted": True, "id": rule_id}
