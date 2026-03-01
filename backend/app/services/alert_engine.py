"""A-R2-6: Smart Alert Engine.

Evaluates alert rules against current data and generates alerts.
Supports: score_threshold, score_change, new_hit, data_quality.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule

logger = structlog.get_logger()


class AlertEngine:
    """Condition-based alert evaluation engine."""

    def __init__(self, session: Session):
        self.session = session

    def evaluate_all_rules(self) -> int:
        """Evaluate all active rules and generate alerts. Returns count created."""
        rules = self.session.query(AlertRule).filter(AlertRule.is_active == True).all()
        alerts_generated = 0

        for rule in rules:
            if self._is_in_cooldown(rule):
                continue

            try:
                if rule.condition_type == "score_threshold":
                    alerts_generated += self._eval_score_threshold(rule)
                elif rule.condition_type == "new_hit":
                    alerts_generated += self._eval_new_hit(rule)
                elif rule.condition_type == "data_quality":
                    alerts_generated += self._eval_data_quality(rule)
                elif rule.condition_type == "score_change":
                    alerts_generated += self._eval_score_change(rule)
            except Exception as e:
                logger.warning("alert_rule_eval_failed", rule_id=rule.id, error=str(e))

        if alerts_generated > 0:
            self.session.flush()

        logger.info("alert_engine_complete", rules_evaluated=len(rules), alerts_generated=alerts_generated)
        return alerts_generated

    def _is_in_cooldown(self, rule: AlertRule) -> bool:
        """Check if the rule is within its cooldown period."""
        last_alert = (
            self.session.query(AlertHistory)
            .filter(AlertHistory.rule_id == rule.id)
            .order_by(AlertHistory.triggered_at.desc())
            .first()
        )
        if last_alert:
            cooldown_end = last_alert.triggered_at + timedelta(minutes=rule.cooldown_minutes)
            return datetime.now(timezone.utc) < cooldown_end
        return False

    def _eval_score_threshold(self, rule: AlertRule) -> int:
        """Detect ads where hit_score crosses the threshold."""
        if not rule.threshold:
            return 0

        op = rule.operator or "gt"
        if op == "gt":
            cond = "::float > :threshold"
        elif op == "lt":
            cond = "::float < :threshold"
        else:
            cond = "::float = :threshold"

        query = f"""
            SELECT a.id, a.advertiser_name,
                   (a.ad_metadata->>'latest_hit_score')::float as score
            FROM ads a
            WHERE a.ad_metadata->>'latest_hit_score' IS NOT NULL
              AND (a.ad_metadata->>'latest_hit_score'){cond}
              AND a.id NOT IN (
                  SELECT ah.ad_id FROM alert_history ah
                  WHERE ah.rule_id = :rule_id
                    AND ah.ad_id IS NOT NULL
                    AND ah.triggered_at > NOW() - INTERVAL '24 hours'
              )
        """

        if rule.genre_filter:
            query += " AND a.ad_metadata->>'fine_genre_en' = :genre"

        query += " LIMIT 10"

        params = {"threshold": rule.threshold, "rule_id": rule.id}
        if rule.genre_filter:
            params["genre"] = rule.genre_filter

        rows = self.session.execute(text(query), params).fetchall()

        count = 0
        for r in rows:
            self._create_alert(
                rule, ad_id=r[0],
                title=f"Hit score alert: {r[1] or 'Unknown'} (score={r[2]:.0f})",
                message=f"Ad #{r[0]} hit_score={r[2]:.1f} {rule.operator or 'gt'} {rule.threshold}",
                new_val=r[2],
            )
            count += 1
        return count

    def _eval_new_hit(self, rule: AlertRule) -> int:
        """Detect newly identified HIT ads (not previously alerted)."""
        rows = self.session.execute(text("""
            SELECT a.id, a.advertiser_name,
                   (a.ad_metadata->>'latest_hit_score')::float as score
            FROM ads a
            WHERE (a.ad_metadata->>'is_hit')::boolean = true
              AND a.id NOT IN (
                  SELECT ah.ad_id FROM alert_history ah
                  WHERE ah.rule_id = :rule_id
                    AND ah.ad_id IS NOT NULL
              )
            LIMIT 10
        """), {"rule_id": rule.id}).fetchall()

        count = 0
        for r in rows:
            self._create_alert(
                rule, ad_id=r[0],
                title=f"New HIT ad: {r[1] or 'Unknown'}",
                message=f"Ad #{r[0]} detected as HIT (score={r[2]:.0f})",
                new_val=r[2],
                severity="info",
            )
            count += 1
        return count

    def _eval_data_quality(self, rule: AlertRule) -> int:
        """Check NULL rates and alert if above threshold."""
        threshold_pct = rule.threshold or 10.0
        total = self.session.query(func.count(Ad.id)).scalar()
        if total == 0:
            return 0

        null_meta = self.session.execute(text(
            "SELECT COUNT(*) FROM ads WHERE ad_metadata IS NULL"
        )).scalar()

        null_pct = null_meta / total * 100
        if null_pct > threshold_pct:
            self._create_alert(
                rule, ad_id=None,
                title=f"Data quality warning: {null_pct:.1f}% NULL metadata",
                message=f"{null_meta}/{total} ads have NULL ad_metadata (threshold: {threshold_pct}%)",
                new_val=null_pct,
                severity="warning",
            )
            return 1
        return 0

    def _eval_score_change(self, rule: AlertRule) -> int:
        """Detect ads with significant score changes (placeholder)."""
        # Would compare current vs previous day's scores
        # Requires score history tracking
        return 0

    def _create_alert(
        self, rule: AlertRule, ad_id: int | None,
        title: str, message: str,
        old_val: float | None = None, new_val: float | None = None,
        severity: str = "info",
    ) -> AlertHistory:
        alert = AlertHistory(
            rule_id=rule.id,
            ad_id=ad_id,
            alert_type=rule.condition_type,
            severity=severity,
            title=title,
            message=message,
            old_value=old_val,
            new_value=new_val,
        )
        self.session.add(alert)
        return alert


def seed_default_rules(session: Session):
    """Create default alert rules if none exist."""
    existing = session.query(func.count(AlertRule.id)).scalar()
    if existing > 0:
        return 0

    defaults = [
        AlertRule(
            name="大HIT候補検出",
            description="hit_score > 80 の広告を検出",
            condition_type="score_threshold",
            target_field="hit_score",
            operator="gt",
            threshold=80.0,
            cooldown_minutes=120,
        ),
        AlertRule(
            name="新HIT広告発見",
            description="新たにHIT判定された広告を通知",
            condition_type="new_hit",
            cooldown_minutes=60,
        ),
        AlertRule(
            name="データ品質警告",
            description="NULL metadata率が10%を超えたら警告",
            condition_type="data_quality",
            threshold=10.0,
            cooldown_minutes=1440,  # 1 day
            notification_channel="in_app",
        ),
    ]

    for rule in defaults:
        session.add(rule)
    session.flush()
    return len(defaults)
