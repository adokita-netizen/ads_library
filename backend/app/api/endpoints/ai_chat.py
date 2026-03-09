"""AI Chat API endpoints."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_sync
from app.core.database import sync_session_scope
from app.models.conversation import Conversation
from app.services.ai.chat_service import ChatService

router = APIRouter(prefix="/ai-chat", tags=["AI Chat"])


class ChatMessageRequest(BaseModel):
    conversation_id: int | None = Field(default=None)
    message: str = Field(..., min_length=1, max_length=4000)


@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    with sync_session_scope() as session:
        svc = ChatService(session=session, user_id=current_user.get("user_id"))
        result = await svc.process_message(
            conversation_id=request.conversation_id,
            message=request.message,
        )
        return result


@router.post("/message/stream")
async def send_message_stream(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    with sync_session_scope() as session:
        svc = ChatService(session=session, user_id=current_user.get("user_id"))
        result = await svc.process_message(
            conversation_id=request.conversation_id,
            message=request.message,
        )

    async def event_stream():
        message = str(result.get("response", {}).get("message", ""))
        chunk_size = 120
        for i in range(0, len(message), chunk_size):
            chunk = message[i : i + chunk_size]
            payload = {"type": "chunk", "delta": chunk}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        final_payload = {"type": "done", "result": result}
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user_sync),
):
    with sync_session_scope() as session:
        base_query = session.query(Conversation).filter(Conversation.user_id == current_user.get("user_id"))
        total = base_query.count()
        rows = (
            base_query.order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        conversations = []
        for row in rows:
            conversations.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "message_count": len(row.messages or []),
                    "last_message_at": _last_message_timestamp(row.messages or []),
                }
            )

        return {"conversations": conversations, "total": total, "limit": limit, "offset": offset}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    with sync_session_scope() as session:
        row = (
            session.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.get("user_id"),
            )
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {
            "id": row.id,
            "title": row.title,
            "messages": row.messages or [],
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    with sync_session_scope() as session:
        row = (
            session.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.get("user_id"),
            )
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        session.delete(row)
        session.commit()
        return {
            "deleted": True,
            "conversation_id": conversation_id,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }


def _last_message_timestamp(messages: list[dict]) -> str | None:
    if not messages:
        return None
    last = messages[-1]
    return str(last.get("timestamp")) if isinstance(last, dict) else None
