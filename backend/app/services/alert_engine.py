"""A-R2-6: Smart Alert Engine.

Evaluates alert rules against current data and generates alerts.
Supports: score_threshold, score_change, new_hit, data_quality.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule

logger = structlog.get_logger()
_RECENT_SCORE_CHANGE_HOURS = 36


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

        op = (rule.operator or "gt").lower()
        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        alerted_ids = {
            r[0]
            for r in self.session.query(AlertHistory.ad_id)
            .filter(
                AlertHistory.rule_id == rule.id,
                AlertHistory.ad_id.isnot(None),
                AlertHistory.triggered_at > cooldown_cutoff,
            )
            .all()
        }

        rows = []
        for ad in self.session.query(Ad).all():
            meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
            if rule.genre_filter and meta.get("fine_genre_en") != rule.genre_filter:
                continue
            raw_score = meta.get("latest_hit_score")
            if raw_score is None:
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            if op == "gt":
                matched = score > float(rule.threshold)
            elif op == "lt":
                matched = score < float(rule.threshold)
            else:
                matched = score == float(rule.threshold)
            if not matched:
                continue
            if ad.id in alerted_ids:
                continue
            rows.append((ad.id, ad.advertiser_name, score))
            if len(rows) >= 10:
                break

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
        alerted_ids = {
            r[0]
            for r in self.session.query(AlertHistory.ad_id)
            .filter(AlertHistory.rule_id == rule.id, AlertHistory.ad_id.isnot(None))
            .all()
        }
        rows = []
        for ad in self.session.query(Ad).all():
            meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
            if not bool(meta.get("is_hit")):
                continue
            if ad.id in alerted_ids:
                continue
            try:
                score = float(meta.get("latest_hit_score", 0) or 0)
            except (TypeError, ValueError):
                score = 0.0
            rows.append((ad.id, ad.advertiser_name, score))
            if len(rows) >= 10:
                break

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

        null_meta = (
            self.session.query(func.count(Ad.id))
            .filter(Ad.ad_metadata.is_(None))
            .scalar()
        )

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
        """Detect ads with significant score changes using metadata score_delta."""
        if rule.threshold is None:
            return 0

        op = (rule.operator or "change_gt").lower()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_RECENT_SCORE_CHANGE_HOURS)
        alerted_ids = {
            r[0]
            for r in self.session.query(AlertHistory.ad_id)
            .filter(
                AlertHistory.rule_id == rule.id,
                AlertHistory.ad_id.isnot(None),
                AlertHistory.triggered_at > cutoff,
            )
            .all()
        }

        rows = []
        for ad in self.session.query(Ad).all():
            meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
            if rule.genre_filter and meta.get("fine_genre_en") != rule.genre_filter:
                continue
            score_updated_at = meta.get("score_updated_at")
            if score_updated_at:
                try:
                    updated_at = datetime.fromisoformat(str(score_updated_at).replace("Z", "+00:00"))
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    if updated_at < cutoff:
                        continue
                except ValueError:
                    continue
            score_delta_raw = meta.get("score_delta", meta.get("hit_score_diff"))
            previous_score_raw = meta.get("previous_hit_score")
            latest_score_raw = meta.get("latest_hit_score")
            if score_delta_raw is None or latest_score_raw is None:
                continue
            try:
                score_delta = float(score_delta_raw)
                previous_score = float(previous_score_raw) if previous_score_raw is not None else None
                latest_score = float(latest_score_raw)
            except (TypeError, ValueError):
                continue
            if ad.id in alerted_ids:
                continue
            if op == "change_gt":
                matched = abs(score_delta) > float(rule.threshold)
            elif op == "gt":
                matched = score_delta > float(rule.threshold)
            elif op == "lt":
                matched = score_delta < float(rule.threshold)
            else:
                matched = abs(score_delta) == float(rule.threshold)
            if not matched:
                continue
            rows.append((ad.id, ad.advertiser_name, previous_score, latest_score, score_delta))
            if len(rows) >= 10:
                break

        count = 0
        for ad_id, advertiser, previous_score, latest_score, score_delta in rows:
            severity = "warning" if abs(score_delta) < 20 else "critical"
            self._create_alert(
                rule,
                ad_id=ad_id,
                title=f"Hit score changed: {advertiser or 'Unknown'} ({score_delta:+.1f})",
                message=f"Ad #{ad_id} hit_score changed from {previous_score or 0:.1f} to {latest_score:.1f}",
                old_val=previous_score,
                new_val=latest_score,
                severity=severity,
            )
            count += 1
        return count

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
        AlertRule(
            name="スコア急変アラート",
            description="score_delta の絶対値が15以上の広告を通知",
            condition_type="score_change",
            operator="change_gt",
            threshold=15.0,
            cooldown_minutes=180,
            notification_channel="in_app",
        ),
    ]

    for rule in defaults:
        session.add(rule)
    session.flush()
    return len(defaults)
