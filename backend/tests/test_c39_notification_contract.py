import asyncio
from contextlib import contextmanager

from app.core import database as db
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule


def _import_module():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints import rankings_notifications
    return rankings_notifications


@contextmanager
def _session_scope(session):
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


def _mk_rule(name: str = "rule-1") -> AlertRule:
    return AlertRule(
        name=name,
        description="desc",
        condition_type="score_threshold",
        target_field="hit_score",
        operator="gt",
        threshold=70,
        genre_filter=None,
        is_active=True,
        notification_channel="in_app",
        cooldown_minutes=60,
        rule_metadata={},
    )


def test_notifications_crud_and_unread_count(session, monkeypatch):
    api = _import_module()
    monkeypatch.setattr(api, "sync_session_scope", lambda: _session_scope(session))
    AlertRule.__table__.create(bind=session.bind, checkfirst=True)
    AlertHistory.__table__.create(bind=session.bind, checkfirst=True)

    rule = _mk_rule("notify-rule")
    session.add(rule)
    session.flush()
    session.add_all(
        [
            AlertHistory(
                rule_id=rule.id,
                alert_type="system",
                severity="info",
                title="n1",
                message="m1",
                is_read=False,
            ),
            AlertHistory(
                rule_id=rule.id,
                alert_type="alert",
                severity="warning",
                title="n2",
                message="m2",
                is_read=True,
            ),
        ]
    )
    session.commit()

    res = asyncio.run(
        api.list_notifications(
            page=1,
            per_page=20,
            unread_only=False,
            type_filter=None,
            current_user={"id": 1},
        )
    )
    assert res["total"] == 2
    assert res["unread_count"] == 1

    unread_only = asyncio.run(
        api.list_notifications(
            page=1,
            per_page=20,
            unread_only=True,
            type_filter=None,
            current_user={"id": 1},
        )
    )
    assert unread_only["total"] == 1

    nid = res["notifications"][0]["id"]
    mark = asyncio.run(api.mark_notification_read(nid, current_user={"id": 1}))
    assert mark["read"] is True

    all_read = asyncio.run(api.mark_all_notifications_read(current_user={"id": 1}))
    assert all_read["updated"] >= 0

    deleted = asyncio.run(api.delete_notification(nid, current_user={"id": 1}))
    assert deleted["deleted"] is True


def test_alert_rule_crud_and_schema(session, monkeypatch):
    api = _import_module()
    monkeypatch.setattr(api, "sync_session_scope", lambda: _session_scope(session))
    AlertRule.__table__.create(bind=session.bind, checkfirst=True)
    AlertHistory.__table__.create(bind=session.bind, checkfirst=True)

    created = asyncio.run(
        api.create_alert_rule(
            api.AlertRuleCreate(
                name="rule-c39",
                condition_type="new_hit",
                target_field="hit_score",
                operator="gt",
                threshold=80,
                metadata={"k": "v"},
            ),
            current_user={"id": 1},
        )
    )
    assert created["name"] == "rule-c39"
    assert created["condition_type"] == "new_hit"
    assert created["metadata"]["k"] == "v"

    listed = asyncio.run(api.list_alert_rules(current_user={"id": 1}))
    assert listed["total"] >= 1
    rule_id = created["id"]

    updated = asyncio.run(
        api.update_alert_rule(
            rule_id,
            api.AlertRuleUpdate(is_active=False, cooldown_minutes=5),
            current_user={"id": 1},
        )
    )
    assert updated["id"] == rule_id
    assert updated["is_active"] is False

    removed = asyncio.run(api.delete_alert_rule(rule_id, current_user={"id": 1}))
    assert removed["deleted"] is True

