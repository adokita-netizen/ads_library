"""C-R2-3 External integration API endpoints."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.api.deps import get_current_user_sync
from app.services.integrations.csv_exporter import CSVExporter
from app.services.integrations.slack_notifier import SlackNotifier
from app.services.integrations.webhook_sender import WebhookSender

router = APIRouter(prefix="/integrations", tags=["Integrations"])

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_SLACK_CONFIG_FILE = _DATA_DIR / "integration_slack_config.json"
_WEBHOOKS_FILE = _DATA_DIR / "integration_webhooks.json"
_SCHEDULED_EXPORT_FILE = _DATA_DIR / "integration_scheduled_exports.json"


class SlackConfigRequest(BaseModel):
    webhook_url: HttpUrl
    channel: Optional[str] = None


class WebhookCreateRequest(BaseModel):
    url: HttpUrl
    events: list[str] = Field(default_factory=list)
    secret: Optional[str] = None
    is_active: bool = True


class ScheduledExportDelivery(BaseModel):
    type: str = Field(..., description="slack, webhook, email")
    target: str = Field(..., min_length=1)


class ScheduledExportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    schedule: str = Field(..., description="daily, weekly, monthly")
    format: str = Field(..., description="csv, json")
    filters: dict = Field(default_factory=dict)
    delivery: ScheduledExportDelivery


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/slack/configure")
async def configure_slack(
    request: SlackConfigRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    data = _load_json(_SLACK_CONFIG_FILE)
    if not isinstance(data, dict):
        data = {}
    data["webhook_url"] = str(request.webhook_url)
    data["channel"] = request.channel
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_by"] = current_user.get("user_id")
    _save_json(_SLACK_CONFIG_FILE, data)
    return {"success": True, "config": {"channel": request.channel, "updated_at": data["updated_at"]}}


@router.post("/slack/test")
async def test_slack(
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    data = _load_json(_SLACK_CONFIG_FILE)
    if not isinstance(data, dict) or not data.get("webhook_url"):
        raise HTTPException(status_code=400, detail="Slack is not configured")

    notifier = SlackNotifier()
    result = await notifier.send_test(webhook_url=str(data["webhook_url"]), channel=data.get("channel"))
    return result


@router.post("/webhooks")
async def create_webhook(
    request: WebhookCreateRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    items = _load_json(_WEBHOOKS_FILE)
    if not isinstance(items, list):
        items = []
    new_id = max((int(i.get("id", 0)) for i in items), default=0) + 1
    now_iso = datetime.now(timezone.utc).isoformat()
    item = {
        "id": new_id,
        "url": str(request.url),
        "events": request.events,
        "secret": request.secret,
        "is_active": request.is_active,
        "created_at": now_iso,
        "updated_at": now_iso,
        "created_by": current_user.get("user_id"),
    }
    items.append(item)
    _save_json(_WEBHOOKS_FILE, items)
    return {"success": True, "webhook": item}


@router.get("/webhooks")
async def list_webhooks(
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    items = _load_json(_WEBHOOKS_FILE)
    if not isinstance(items, list):
        items = []
    masked = []
    for i in items:
        masked.append(
            {
                "id": i.get("id"),
                "url": i.get("url"),
                "events": i.get("events", []),
                "is_active": bool(i.get("is_active", True)),
                "has_secret": bool(i.get("secret")),
                "created_at": i.get("created_at"),
                "updated_at": i.get("updated_at"),
            }
        )
    return {"webhooks": masked, "total": len(masked)}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    _ = current_user
    items = _load_json(_WEBHOOKS_FILE)
    if not isinstance(items, list):
        items = []
    before = len(items)
    items = [i for i in items if int(i.get("id", -1)) != webhook_id]
    if len(items) == before:
        raise HTTPException(status_code=404, detail="Webhook not found")
    _save_json(_WEBHOOKS_FILE, items)
    return {"success": True, "deleted_id": webhook_id}


@router.post("/scheduled-export")
async def create_scheduled_export(
    request: ScheduledExportRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    items = _load_json(_SCHEDULED_EXPORT_FILE)
    if not isinstance(items, list):
        items = []

    exporter = CSVExporter()
    try:
        config = exporter.build_config(
            name=request.name,
            schedule=request.schedule,
            export_format=request.format,
            filters=request.filters,
            delivery=request.delivery.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    new_id = max((int(i.get("id", 0)) for i in items), default=0) + 1
    config["id"] = new_id
    config["created_by"] = current_user.get("user_id")
    items.append(config)
    _save_json(_SCHEDULED_EXPORT_FILE, items)

    # Best-effort immediate webhook ping when delivery type is webhook
    delivery_type = config.get("delivery", {}).get("type")
    if delivery_type == "webhook":
        sender = WebhookSender()
        _ = await sender.send(
            webhook_url=config["delivery"]["target"],
            event="scheduled_export_created",
            payload={"id": config["id"], "name": config["name"], "schedule": config["schedule"]},
            secret=None,
        )

    return {"success": True, "scheduled_export": config}

