import asyncio
from contextlib import contextmanager

from app.core import database as db
from app.models.conversation import Conversation


def _import_modules():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.services.ai.chat_service import ChatService
    from app.services.ai.intent_classifier import IntentClassifier
    return ChatService, IntentClassifier


def test_intent_classifier_basic_routes():
    _, IntentClassifier = _import_modules()
    clf = IntentClassifier()
    assert clf.classify("何件ありますか？") == "data_stats"
    assert clf.classify("最近のトレンドを教えて") == "find_trends"
    assert clf.classify("この広告 ad 123 を分析して") == "analyze_ad"


def test_chat_service_rule_based_persists_conversation(session, monkeypatch):
    ChatService, _ = _import_modules()
    Conversation.__table__.create(bind=session.bind, checkfirst=True)

    # Avoid external provider dependency in contract test.
    monkeypatch.setattr(ChatService, "_get_claude_client", lambda self: None)

    svc = ChatService(session=session, user_id=101)
    first = asyncio.run(svc.process_message(conversation_id=None, message="何件ありますか？"))

    assert "conversation_id" in first
    assert first["response"]["provider"] == "rule_based"
    assert "actions" in first["response"]
    assert "related_ad_ids" in first["response"]
    cid = first["conversation_id"]

    row = session.query(Conversation).filter(Conversation.id == cid).first()
    assert row is not None
    assert row.user_id == 101
    assert isinstance(row.messages, list)
    assert len(row.messages) == 2

    second = asyncio.run(svc.process_message(conversation_id=cid, message="最近のトレンドは？"))
    assert second["conversation_id"] == cid
    row2 = session.query(Conversation).filter(Conversation.id == cid).first()
    assert row2 is not None
    assert len(row2.messages) == 4


def test_chat_service_claude_path_returns_usage(session, monkeypatch):
    ChatService, _ = _import_modules()
    Conversation.__table__.create(bind=session.bind, checkfirst=True)

    class _FakeClaude:
        async def generate_message(self, **_kwargs):
            return {
                "ok": True,
                "message": "Claude回答です",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }

    monkeypatch.setattr(ChatService, "_get_claude_client", lambda self: _FakeClaude())

    svc = ChatService(session=session, user_id=202)
    res = asyncio.run(svc.process_message(conversation_id=None, message="美容ジャンルの分析をして"))
    assert res["response"]["provider"] == "claude"
    assert res["response"]["message"] == "Claude回答です"
    assert res["response"]["usage"]["output_tokens"] == 20

