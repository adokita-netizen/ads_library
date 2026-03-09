"""C-R2-2 notification service for in-app alerts."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule


class NotificationService:
    """Utility service to create and dispatch in-app notifications."""

    SYSTEM_RULE_NAME = "_system_notification_rule"

    def __init__(self, session: Session):
        self.session = session

    def _ensure_system_rule(self) -> AlertRule:
        """AlertHistory requires rule_id, so keep a shared system rule."""
        rule = (
            self.session.query(AlertRule)
            .filter(AlertRule.name == self.SYSTEM_RULE_NAME)
            .first()
        )
        if rule:
            return rule

        rule = AlertRule(
            name=self.SYSTEM_RULE_NAME,
            description="System-generated notification holder",
            condition_type="system",
            target_field=None,
            operator=None,
            threshold=None,
            genre_filter=None,
            is_active=False,
            notification_channel="in_app",
            cooldown_minutes=0,
        )
        self.session.add(rule)
        self.session.flush()
        return rule

    def create_notification(
        self,
        notif_type: str,
        title: str,
        body: str,
        ad_id: int | None = None,
        severity: str = "info",
        metadata: dict | None = None,
    ) -> AlertHistory:
        """Create an AlertHistory row as in-app notification."""
        system_rule = self._ensure_system_rule()
        alert = AlertHistory(
            rule_id=system_rule.id,
            ad_id=ad_id,
            alert_type=notif_type,
            severity=severity,
            title=title,
            message=body,
            alert_metadata=metadata or {},
        )
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        return alert

    def notify_crawl_complete(self, new_count: int, total: int) -> AlertHistory:
        return self.create_notification(
            notif_type="system",
            title="Crawl completed",
            body=f"{new_count} new ads collected. Total: {total}",
            severity="info",
            metadata={"new_count": new_count, "total": total},
        )

    def notify_new_hit(self, ad_id: int, ad_title: str, score: float) -> AlertHistory:
        return self.create_notification(
            notif_type="new_ad",
            title="New HIT ad detected",
            body=f"'{ad_title}' scored {score:.1f}",
            ad_id=ad_id,
            severity="info",
            metadata={"score": score},
        )

    def notify_score_change(
        self,
        ad_id: int,
        ad_title: str,
        old_score: float,
        new_score: float,
    ) -> AlertHistory:
        delta = new_score - old_score
        return self.create_notification(
            notif_type="alert",
            title="Score significant change",
            body=f"'{ad_title}' score changed by {delta:+.1f} ({old_score:.1f} -> {new_score:.1f})",
            ad_id=ad_id,
            severity="warning" if abs(delta) > 20 else "info",
            metadata={"old_score": old_score, "new_score": new_score, "delta": delta},
        )

    def mark_all_as_read(self) -> int:
        """Mark all unread notifications as read. Returns affected row count."""
        now = datetime.now(timezone.utc)
        count = (
            self.session.query(AlertHistory)
            .filter(AlertHistory.is_read.is_(False))
            .update(
                {
                    AlertHistory.is_read: True,
                    AlertHistory.read_at: now,
                },
                synchronize_session=False,
            )
        )
        self.session.commit()
        return int(count or 0)

