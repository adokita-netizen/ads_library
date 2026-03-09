"""A45 full-cycle data taskpack orchestration."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.models.ad import Ad, MediaExtractionStatus
from app.tasks.metrics_tasks import build_false_negative_hunt_report
from scripts.audit_ads_volume_errors import build_ads_volume_health_report, build_daily_recovery_plan


def should_trigger_auto_recrawl(volume_report: dict) -> bool:
    summary = (volume_report or {}).get("summary") or {}
    target_met = bool(summary.get("target_met_previous_day"))
    previous_day_new_ads = int(summary.get("previous_day_new_ads") or 0)
    target_min = int((volume_report or {}).get("target_min_ads_per_day") or 0)
    return (not target_met) or (target_min > 0 and previous_day_new_ads < target_min)


def build_dictionary_update_plan(session, *, target_date: date | None = None, top_n: int = 20) -> dict:
    rows: list[dict] = []
    term_counter: Counter[tuple[str, str]] = Counter()

    for ad in session.query(Ad).all():
        meta = ad.ad_metadata or {}
        topic = str(meta.get("topic_label") or "").strip().lower()
        if not topic:
            continue
        suggestions = meta.get("topic_dictionary_suggestions") if isinstance(meta.get("topic_dictionary_suggestions"), list) else []
        evidence = meta.get("topic_evidence") if isinstance(meta.get("topic_evidence"), list) else []
        for row in suggestions:
            if not isinstance(row, dict):
                continue
            if target_date and str(row.get("date")) != target_date.isoformat():
                continue
            for term in row.get("terms") or []:
                normalized = str(term).strip().lower()
                if len(normalized) >= 2:
                    term_counter[(topic, normalized)] += 1
        for term in evidence:
            normalized = str(term).strip().lower()
            if len(normalized) >= 2:
                term_counter[(topic, normalized)] += 1

    for (topic, term), count in term_counter.most_common(top_n):
        rows.append(
            {
                "topic_label": topic,
                "term": term,
                "count": count,
                "suggested_decision": "adopt" if count >= 2 else "hold",
                "reason": "full_cycle_dictionary_update",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_terms": rows,
        "summary": {
            "candidate_count": len(rows),
            "adopt_recommended_count": sum(1 for row in rows if row["suggested_decision"] == "adopt"),
        },
    }


def process_failed_record_queue(session, *, max_media_retries: int = 3) -> dict:
    replay_queue: list[int] = []
    quarantined_ids: list[int] = []
    quarantine_reason_counts: Counter[str] = Counter()

    for ad in session.query(Ad).all():
        meta = dict(ad.ad_metadata or {})
        changed = False

        if ad.media_extraction_status == MediaExtractionStatus.FAILED:
            retry_count = int(meta.get("media_retry_count") or 0)
            if retry_count >= max_media_retries:
                meta["quarantine_reason"] = "media_retry_exhausted"
                meta["quarantined_at"] = datetime.now(timezone.utc).isoformat()
                quarantined_ids.append(ad.id)
                quarantine_reason_counts["media_retry_exhausted"] += 1
                changed = True
            else:
                meta["needs_media_retry"] = True
                replay_queue.append(ad.id)
                changed = True

        missing_reasons = meta.get("incomplete_reason") if isinstance(meta.get("incomplete_reason"), list) else []
        if meta.get("is_incomplete_record") and len(missing_reasons) >= 2:
            meta["quarantine_reason"] = "missing_fields_unrecoverable"
            meta["quarantined_at"] = datetime.now(timezone.utc).isoformat()
            quarantined_ids.append(ad.id)
            quarantine_reason_counts["missing_fields_unrecoverable"] += 1
            changed = True

        if changed:
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

    session.flush()
    return {
        "replay_queue_ad_ids": sorted(set(replay_queue)),
        "replay_queue_count": len(set(replay_queue)),
        "quarantined_ad_ids": sorted(set(quarantined_ids)),
        "quarantined_count": len(set(quarantined_ids)),
        "quarantine_reason_counts": dict(quarantine_reason_counts),
    }


def run_full_cycle_data_taskpack(
    session,
    *,
    target_date: date | None = None,
    focus_keywords: list[str] | None = None,
    target_min_ads_per_day: int = 100,
    queue_recrawls: bool = False,
) -> dict:
    target_date = target_date or date.today()
    volume_report = build_ads_volume_health_report(
        session,
        days=7,
        min_ads=5,
        target_min_ads_per_day=target_min_ads_per_day,
    )
    false_negative_hunt = build_false_negative_hunt_report(
        session,
        target_date=target_date,
        false_negative_limit=20,
        queue_recrawls=queue_recrawls,
    )
    dictionary_update = build_dictionary_update_plan(session, target_date=target_date, top_n=20)
    failed_record_queue = process_failed_record_queue(session)

    auto_recrawl_plan = build_daily_recovery_plan(
        previous_day_new_ads=int(volume_report["summary"]["previous_day_new_ads"]),
        target_min_ads_per_day=target_min_ads_per_day,
        focus_keywords=focus_keywords or [row.get("term", "") for row in dictionary_update["candidate_terms"][:3] if row.get("term")],
        execute_recovery=False,
        api_base="http://localhost:8000/api/v1",
        recovery_limit=20,
        timeout_sec=30,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "auto_recrawl": {
            "should_trigger": should_trigger_auto_recrawl(volume_report),
            "recovery_plan": auto_recrawl_plan,
        },
        "dictionary_update": dictionary_update,
        "false_negative_hunt": false_negative_hunt,
        "failed_record_queue": failed_record_queue,
    }
