"""Version 2 API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_sync
from app.core.database import sync_session_scope
from app.services.ai.chat_service import ChatService

router = APIRouter(tags=["v2"])


class V2ChatMessageRequest(BaseModel):
    conversation_id: int | None = Field(default=None)
    message: str = Field(..., min_length=1, max_length=4000)


@router.get("/version")
async def api_version():
    return {
        "version": "v2",
        "status": "active",
        "breaking_changes": [
            "ai-chat response format changed (v1.response -> v2.assistant/analysis)",
        ],
        "v1_deprecation": {
            "deprecated": True,
            "sunset_date": "2026-06-30",
            "migration_doc": "/api/v2/version",
        },
    }


@router.post("/ai-chat/message")
async def send_message_v2(
    request: V2ChatMessageRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    with sync_session_scope() as session:
        svc = ChatService(session=session, user_id=current_user.get("user_id"))
        result = await svc.process_message(
            conversation_id=request.conversation_id,
            message=request.message,
        )

    response = result.get("response", {}) if isinstance(result, dict) else {}
    return {
        "meta": {
            "api_version": "v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "conversation": {"id": result.get("conversation_id")},
        "assistant": {
            "content": response.get("message", ""),
            "intent": response.get("intent"),
            "provider": response.get("provider", "rule_based"),
            "usage": response.get("usage", {}),
        },
        "analysis": {
            "data": response.get("data", {}),
            "actions": response.get("actions", []),
            "related_ad_ids": response.get("related_ad_ids", []),
        },
    }
