"""Creative library and live-ingestion audit helpers for daily KPI reporting."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.utils.text import japanese_text_ratio

_AUDIT_REPORTS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "creative_library_audit_reports.json"
_MAX_HISTORY = 30
_DEFAULT_TOP_N = 20
_STALE_WINDOW_DAYS = 7
_SLO_THRESHOLDS = {
    "creative_viewable_rate": 0.9,
    "creative_downloadable_rate": 0.75,
    "lp_resolved_rate": 0.7,
}
_NEGATIVE_DELTA_WARNING = -0.03
_NEGATIVE_DELTA_CRITICAL = -0.08
_BUCKET_DROP_WARNING = -0.1
_ADVERTISER_CONCENTRATION_WARNING = 0.45
_NUMERIC_FIELDS = ("spend", "impressions", "reach", "view_count", "lp_score", "extract_quality_score")
_ESTIMATED_METHOD_TOKENS = (
    "estimate",
    "estimated",
    "audience",
    "cpm",
    "default",
    "heuristic",
    "inferred",
    "model",
)
_JP_STRONG_THRESHOLD = 0.2
_JP_WEAK_THRESHOLD = 0.02
_BEDROCK_SOURCE_TOKENS = ("bedrock", "ai", "llm", "claude", "comprehend")
_HIGH_CONFIDENCE_THRESHOLD = 0.8
_HIGH_PRIORITY_THRESHOLD = 55.0
_META_PLATFORMS = {"facebook", "instagram"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _platform_label(ad: Ad) -> str:
    platform = getattr(ad, "platform", None)
    if platform is None:
        return "unknown"
    return _as_text(getattr(platform, "value", platform)).lower() or "unknown"


def _genre_label(ad: Ad) -> str:
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    for key in ("genre", "genre_ja", "topic_label"):
        value = _as_text(meta.get(key))
        if value:
            return value
    category = getattr(ad, "category", None)
    return _as_text(getattr(category, "value", category)).lower() or "unknown"


def _advertiser_label(ad: Ad) -> str:
    return _as_text(getattr(ad, "advertiser_name", None)) or "unknown"


def _keyword_label(ad: Ad) -> str:
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    for key in ("last_crawl_keyword", "search_terms", "keyword", "query"):
        value = _as_text(meta.get(key))
        if value:
            return value.lower()
    return "unknown"


def _has_local_cached_file(meta: dict) -> bool:
    for key in (
        "local_cached_file",
        "local_cache_path",
        "thumbnail_local_path",
        "image_local_path",
        "video_local_path",
    ):
        if _as_text(meta.get(key)):
            return True
    return False


def _is_stale_creative(meta: dict) -> bool:
    snapshot = meta.get("snapshot_check") if isinstance(meta.get("snapshot_check"), dict) else {}
    if snapshot.get("reachable") is False:
        return True
    if _as_text(meta.get("creative_fetch_reason")) in {"blocked_or_expired", "not_found_in_api"}:
        return True
    return False


def _has_lp_present(ad: Ad, meta: dict) -> bool:
    lp_data = meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}
    return bool(
        ad.destination_url
        or meta.get("destination_url")
        or meta.get("lp_final_url")
        or meta.get("final_url")
        or lp_data.get("url")
        or lp_data.get("final_url")
    )


def _is_lp_resolved(meta: dict) -> bool:
    lp_data = meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}
    lp_analysis = meta.get("lp_analysis") if isinstance(meta.get("lp_analysis"), dict) else {}
    return bool(
        meta.get("lp_final_url")
        or meta.get("final_url")
        or lp_data.get("final_url")
        or lp_data.get("url")
        or lp_data.get("title")
        or lp_data.get("meta_description")
        or lp_analysis.get("final_url")
        or lp_analysis.get("title")
    )


def _is_active(ad: Ad, meta: dict, *, target_date: date) -> bool:
    status = meta.get("is_still_running")
    if status is True:
        return True
    if status is False:
        return False
    last_seen = _to_datetime(getattr(ad, "last_seen_at", None) or meta.get("last_checked_at"))
    if last_seen is None:
        return False
    return last_seen.date() >= (target_date - timedelta(days=_STALE_WINDOW_DAYS))


def _new_ad_date(ad: Ad) -> date | None:
    first_seen = _to_datetime(getattr(ad, "first_seen_at", None))
    created_at = _to_datetime(getattr(ad, "created_at", None))
    candidate = first_seen or created_at
    return candidate.date() if candidate else None


def _stale_date(ad: Ad, meta: dict) -> date | None:
    last_seen = _to_datetime(getattr(ad, "last_seen_at", None))
    if last_seen:
        return last_seen.date()
    freshness_updated = _to_datetime(meta.get("freshness_updated_at"))
    return freshness_updated.date() if freshness_updated else None


def _dedupe_signature(row: dict) -> str:
    return "|".join(
        [
            _as_text(row.get("platform")).lower(),
            _as_text(row.get("advertiser")).lower(),
            _as_text(row.get("keyword")).lower(),
            _as_text(row.get("title")).lower(),
        ]
    )


def _build_priority_score(row: dict, *, target_date: date) -> float:
    updated_at = _to_datetime(row.get("updated_at"))
    age_days = 30
    if updated_at is not None:
        age_days = max(0, (target_date - updated_at.date()).days)
    recency_score = max(0.0, 30.0 - min(age_days, 30))
    spend_score = min(float(row.get("spend") or 0.0), 100_000.0) / 1000.0
    active_score = 25.0 if row.get("is_active") else 0.0
    issue_score = 18.0 * len(row.get("failure_reason_codes") or [])
    platform_bonus = 4.0 if row.get("platform") in {"facebook", "instagram", "youtube", "tiktok"} else 1.0
    return round(issue_score + recency_score + spend_score + active_score + platform_bonus, 3)


def _bucket_labels(limit: int, items: dict[str, dict]) -> list[dict]:
    rows = [_finalize_bucket(row) for row in items.values()]
    rows.sort(key=lambda item: (-item["total_ads"], item["label"]))
    return rows[:limit]


def _build_ad_audit_row(ad: Ad, *, target_date: date) -> dict:
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    has_viewable_creative = bool(
        ad.thumbnail_url
        or ad.image_url
        or ad.video_url
        or ad.thumbnail_s3_key
        or ad.image_s3_key
        or ad.s3_key
    )
    has_downloadable_creative = bool(
        ad.image_s3_key
        or ad.s3_key
        or _has_local_cached_file(meta)
    )
    has_lp = _has_lp_present(ad, meta)
    lp_resolved = _is_lp_resolved(meta)
    stale_creative = _is_stale_creative(meta)
    is_active = _is_active(ad, meta, target_date=target_date)

    missing_reasons: list[str] = []
    failure_reason_codes: list[str] = []
    if not has_viewable_creative:
        missing_reasons.append("missing_media")
        failure_reason_codes.append("missing_creative")
    if has_viewable_creative and not has_downloadable_creative:
        missing_reasons.append("download_unavailable")
        failure_reason_codes.append("not_downloadable")
    if not has_lp:
        missing_reasons.append("missing_lp")
        failure_reason_codes.append("missing_lp")
    elif not lp_resolved:
        failure_reason_codes.append("lp_unresolved")
    if stale_creative:
        missing_reasons.append("stale_creative")
        failure_reason_codes.append("stale_snapshot")

    row = {
        "ad_id": ad.id,
        "title": ad.title or "",
        "platform": _platform_label(ad),
        "genre": _genre_label(ad),
        "advertiser": _advertiser_label(ad),
        "keyword": _keyword_label(ad),
        "updated_at": ad.updated_at.isoformat() if getattr(ad, "updated_at", None) else None,
        "first_seen_at": ad.first_seen_at.isoformat() if getattr(ad, "first_seen_at", None) else None,
        "last_seen_at": ad.last_seen_at.isoformat() if getattr(ad, "last_seen_at", None) else None,
        "spend": round(float(getattr(ad, "spend", 0.0) or 0.0), 2),
        "is_active": is_active,
        "has_viewable_creative": has_viewable_creative,
        "has_downloadable_creative": has_downloadable_creative,
        "has_lp": has_lp,
        "lp_resolved": lp_resolved,
        "stale_creative": stale_creative,
        "missing_reasons": missing_reasons,
        "failure_reason_codes": list(dict.fromkeys(failure_reason_codes)),
    }
    row["needs_cr_recovery"] = "missing_creative" in row["failure_reason_codes"] or "stale_snapshot" in row["failure_reason_codes"]
    row["needs_download_recovery"] = "not_downloadable" in row["failure_reason_codes"]
    row["needs_lp_resolution"] = "missing_lp" in row["failure_reason_codes"] or "lp_unresolved" in row["failure_reason_codes"]
    row["priority_score"] = _build_priority_score(row, target_date=target_date)
    return row


def _empty_bucket(label: str) -> dict:
    return {
        "label": label,
        "total_ads": 0,
        "active_ads": 0,
        "spend_total": 0.0,
        "viewable_count": 0,
        "downloadable_count": 0,
        "lp_present_count": 0,
        "lp_resolved_count": 0,
        "missing_media_count": 0,
        "missing_lp_count": 0,
        "lp_unresolved_count": 0,
        "stale_creative_count": 0,
        "download_unavailable_count": 0,
    }


def _finalize_bucket(bucket: dict) -> dict:
    total = int(bucket["total_ads"])

    def _rate(key: str) -> float:
        if total == 0:
            return 0.0
        return round(bucket[key] / total, 4)

    bucket["spend_total"] = round(float(bucket["spend_total"]), 2)
    bucket["creative_viewable_rate"] = _rate("viewable_count")
    bucket["creative_downloadable_rate"] = _rate("downloadable_count")
    bucket["lp_present_rate"] = _rate("lp_present_count")
    bucket["lp_resolved_rate"] = _rate("lp_resolved_count")
    bucket["active_rate"] = _rate("active_ads")
    return bucket


def _compute_delta(current: dict, previous: dict | None) -> dict:
    if not previous:
        return {}
    keys = (
        "creative_viewable_rate",
        "creative_downloadable_rate",
        "lp_present_rate",
        "lp_resolved_rate",
        "estimated_only_count",
        "missing_numeric_count",
        "stale_real_metrics_count",
        "missing_media_count",
        "missing_lp_count",
        "lp_unresolved_count",
        "download_unavailable_count",
        "stale_creative_count",
        "total_ads",
    )
    delta: dict[str, float | int] = {}
    for key in keys:
        if key in current and key in previous:
            value = current[key] - previous[key]
            delta[key] = round(value, 4) if isinstance(value, float) else value
    return delta


def _compute_breakdown_deltas(current_rows: list[dict], previous_rows: list[dict] | None) -> list[dict]:
    if not previous_rows:
        return []
    previous_map = {
        row.get("label"): row
        for row in previous_rows
        if isinstance(row, dict) and row.get("label")
    }
    deltas: list[dict] = []
    for row in current_rows:
        label = row.get("label")
        if not label or label not in previous_map:
            continue
        delta = _compute_delta(row, previous_map[label])
        if delta:
            deltas.append({"label": label, **delta})
    deltas.sort(
        key=lambda item: (
            item.get("creative_viewable_rate", 0.0),
            item.get("creative_downloadable_rate", 0.0),
            item.get("lp_resolved_rate", 0.0),
        )
    )
    return deltas


def _load_history() -> list[dict]:
    if not _AUDIT_REPORTS_FILE.exists():
        return []
    try:
        payload = json.loads(_AUDIT_REPORTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _persist_report(report: dict) -> list[dict]:
    history = [row for row in _load_history() if isinstance(row, dict) and row.get("date") != report["date"]]
    history.append(report)
    _AUDIT_REPORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _AUDIT_REPORTS_FILE.write_text(json.dumps(history[-_MAX_HISTORY:], ensure_ascii=False, indent=2), encoding="utf-8")
    return history[-_MAX_HISTORY:]


def _accumulate_bucket(bucket: dict, row: dict) -> None:
    bucket["total_ads"] += 1
    bucket["active_ads"] += int(row["is_active"])
    bucket["spend_total"] += float(row.get("spend") or 0.0)
    bucket["viewable_count"] += int(row["has_viewable_creative"])
    bucket["downloadable_count"] += int(row["has_downloadable_creative"])
    bucket["lp_present_count"] += int(row["has_lp"])
    bucket["lp_resolved_count"] += int(row["lp_resolved"])
    if "missing_creative" in row["failure_reason_codes"]:
        bucket["missing_media_count"] += 1
    if "missing_lp" in row["failure_reason_codes"]:
        bucket["missing_lp_count"] += 1
    if "lp_unresolved" in row["failure_reason_codes"]:
        bucket["lp_unresolved_count"] += 1
    if "stale_snapshot" in row["failure_reason_codes"]:
        bucket["stale_creative_count"] += 1
    if "not_downloadable" in row["failure_reason_codes"]:
        bucket["download_unavailable_count"] += 1


def _state_signature(row: dict) -> int:
    return (
        int(bool(row.get("has_viewable_creative")))
        + int(bool(row.get("has_downloadable_creative")))
        + int(bool(row.get("has_lp")))
        + int(bool(row.get("lp_resolved")))
    )


def _collect_change_details(current_row: dict, previous_row: dict) -> list[str]:
    changes: list[str] = []
    checks = (
        ("has_viewable_creative", "creative_viewable"),
        ("has_downloadable_creative", "creative_downloadable"),
        ("has_lp", "lp_present"),
        ("lp_resolved", "lp_resolved"),
    )
    for key, label in checks:
        before = bool(previous_row.get(key))
        after = bool(current_row.get(key))
        if before != after:
            changes.append(f"{label}:{'up' if after else 'down'}")
    return changes


def _build_daily_report(rows: list[dict], previous: dict | None) -> dict:
    previous_rows = previous.get("ad_rows") if isinstance(previous, dict) else None
    previous_map = {
        row.get("ad_id"): row
        for row in (previous_rows or [])
        if isinstance(row, dict) and row.get("ad_id") is not None
    }
    regressions: list[dict] = []
    recoveries: list[dict] = []
    for row in rows:
        prev = previous_map.get(row["ad_id"])
        if not prev:
            continue
        score_delta = _state_signature(row) - _state_signature(prev)
        if score_delta == 0:
            continue
        payload = {
            "ad_id": row["ad_id"],
            "title": row["title"],
            "platform": row["platform"],
            "advertiser": row["advertiser"],
            "keyword": row["keyword"],
            "score_delta": score_delta,
            "changed_dimensions": _collect_change_details(row, prev),
            "current_failure_reason_codes": row["failure_reason_codes"],
            "priority_score": row["priority_score"],
        }
        if score_delta < 0:
            regressions.append(payload)
        else:
            recoveries.append(payload)
    regressions.sort(key=lambda item: (item["score_delta"], -item["priority_score"]))
    recoveries.sort(key=lambda item: (-item["score_delta"], -item["priority_score"]))

    return {
        "summary_delta": _compute_delta(
            rows and _finalize_bucket({
                "label": "summary",
                "total_ads": len(rows),
                "active_ads": sum(int(row["is_active"]) for row in rows),
                "spend_total": sum(float(row.get("spend") or 0.0) for row in rows),
                "viewable_count": sum(int(row["has_viewable_creative"]) for row in rows),
                "downloadable_count": sum(int(row["has_downloadable_creative"]) for row in rows),
                "lp_present_count": sum(int(row["has_lp"]) for row in rows),
                "lp_resolved_count": sum(int(row["lp_resolved"]) for row in rows),
                "missing_media_count": sum(int("missing_creative" in row["failure_reason_codes"]) for row in rows),
                "missing_lp_count": sum(int("missing_lp" in row["failure_reason_codes"]) for row in rows),
                "lp_unresolved_count": sum(int("lp_unresolved" in row["failure_reason_codes"]) for row in rows),
                "stale_creative_count": sum(int("stale_snapshot" in row["failure_reason_codes"]) for row in rows),
                "download_unavailable_count": sum(int("not_downloadable" in row["failure_reason_codes"]) for row in rows),
            }),
            previous.get("summary") if isinstance(previous, dict) else None,
        ),
        "top_regressions": regressions[:10],
        "top_recoveries": recoveries[:10],
    }


def _segment_worsening(
    scope: str,
    current_rows: list[dict],
    previous_rows: list[dict] | None,
) -> list[dict]:
    if not previous_rows:
        return []
    previous_map = {
        row.get("label"): row
        for row in previous_rows
        if isinstance(row, dict) and row.get("label")
    }
    worsening: list[dict] = []
    for row in current_rows:
        prev = previous_map.get(row.get("label"))
        if not prev:
            continue
        for metric in ("creative_viewable_rate", "creative_downloadable_rate", "lp_present_rate", "lp_resolved_rate"):
            delta = round(row.get(metric, 0.0) - prev.get(metric, 0.0), 4)
            if delta < 0:
                worsening.append(
                    {
                        "scope": scope,
                        "label": row.get("label"),
                        "metric": metric,
                        "delta": delta,
                        "current": row.get(metric, 0.0),
                        "previous": prev.get(metric, 0.0),
                    }
                )
    worsening.sort(key=lambda item: item["delta"])
    return worsening


def _classify_severity(current: float, threshold: float, delta: float | None) -> str:
    if current < (threshold - 0.1) or (delta is not None and delta <= _NEGATIVE_DELTA_CRITICAL):
        return "critical"
    if current < threshold or (delta is not None and delta <= _NEGATIVE_DELTA_WARNING):
        return "warning"
    return "ok"


def _build_ops_alerts(report: dict, previous: dict | None) -> tuple[dict, list[dict]]:
    summary = report["summary"]
    prev_summary = previous.get("summary") if isinstance(previous, dict) else None
    alerts: list[dict] = []
    slo_status: dict[str, dict] = {}

    for metric, threshold in _SLO_THRESHOLDS.items():
        current = float(summary.get(metric, 0.0))
        delta = None
        if isinstance(prev_summary, dict) and metric in prev_summary:
            delta = round(current - float(prev_summary.get(metric, 0.0)), 4)
        severity = _classify_severity(current, threshold, delta)
        slo_status[metric] = {
            "current": round(current, 4),
            "threshold": threshold,
            "delta_vs_previous_day": delta,
            "severity": severity,
        }
        if severity != "ok":
            alerts.append(
                {
                    "severity": severity,
                    "code": f"{metric}_slo",
                    "scope": "summary",
                    "metric": metric,
                    "current": round(current, 4),
                    "threshold": threshold,
                    "delta_vs_previous_day": delta,
                    "message": f"{metric} dropped to {current:.2%} against SLO {threshold:.0%}",
                }
            )

    for scope in ("platform_breakdown", "advertiser_breakdown"):
        worsening = _segment_worsening(scope, report.get(scope, []), previous.get(scope) if isinstance(previous, dict) else None)
        for item in worsening[:5]:
            if item["delta"] <= _BUCKET_DROP_WARNING:
                severity = "critical" if item["delta"] <= _NEGATIVE_DELTA_CRITICAL else "warning"
                alerts.append(
                    {
                        "severity": severity,
                        "code": f"{scope}_drop",
                        "scope": scope,
                        "label": item["label"],
                        "metric": item["metric"],
                        "current": item["current"],
                        "delta_vs_previous_day": item["delta"],
                        "message": f"{scope}:{item['label']} degraded on {item['metric']}",
                    }
                )

    failing_rows = [row for row in report.get("ad_rows", []) if row.get("failure_reason_codes")]
    advertiser_fail_counts: dict[str, int] = {}
    for row in failing_rows:
        advertiser_fail_counts[row["advertiser"]] = advertiser_fail_counts.get(row["advertiser"], 0) + 1
    if failing_rows and advertiser_fail_counts:
        top_advertiser, fail_count = max(advertiser_fail_counts.items(), key=lambda item: item[1])
        concentration = fail_count / len(failing_rows)
        if concentration >= _ADVERTISER_CONCENTRATION_WARNING and fail_count >= 3:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "advertiser_failure_concentration",
                    "scope": "advertiser",
                    "label": top_advertiser,
                    "current": round(concentration, 4),
                    "threshold": _ADVERTISER_CONCENTRATION_WARNING,
                    "message": f"{top_advertiser} accounts for {concentration:.0%} of current creative failures",
                }
            )

    overall_status = "ok"
    if any(alert["severity"] == "critical" for alert in alerts):
        overall_status = "critical"
    elif alerts:
        overall_status = "warning"

    return {
        "thresholds": dict(_SLO_THRESHOLDS),
        "overall_status": overall_status,
        "metrics": slo_status,
        "warning_count": sum(1 for alert in alerts if alert["severity"] == "warning"),
        "critical_count": sum(1 for alert in alerts if alert["severity"] == "critical"),
    }, alerts


def _load_expected_keywords() -> list[str]:
    try:
        from app.tasks.crawl_tasks import get_today_keywords

        return list(dict.fromkeys(get_today_keywords(prioritize_stale=False)))
    except Exception:
        return []


def _build_live_ingestion_audit(rows: list[dict], *, target_date: date) -> dict:
    new_rows = [row for row in rows if _new_ad_date_proxy(row) == target_date]
    unique_signatures = {_dedupe_signature(row) for row in new_rows}
    stale_cutoff = target_date - timedelta(days=_STALE_WINDOW_DAYS)
    stale_count = 0
    for row in rows:
        last_seen = _to_datetime(row.get("last_seen_at"))
        freshness_score = row.get("freshness_score")
        if last_seen and last_seen.date() < stale_cutoff:
            stale_count += 1
        elif isinstance(freshness_score, (int, float)) and freshness_score < 30:
            stale_count += 1

    platform_counts: dict[str, int] = {}
    advertiser_counts: dict[str, int] = {}
    keyword_counts: dict[str, int] = {}
    recent_keyword_dates: dict[str, date] = {}
    for row in rows:
        first_seen = _new_ad_date_proxy(row)
        if first_seen is not None:
            keyword = row["keyword"]
            if keyword != "unknown":
                latest = recent_keyword_dates.get(keyword)
                if latest is None or first_seen > latest:
                    recent_keyword_dates[keyword] = first_seen
        if first_seen != target_date:
            continue
        platform_counts[row["platform"]] = platform_counts.get(row["platform"], 0) + 1
        advertiser_counts[row["advertiser"]] = advertiser_counts.get(row["advertiser"], 0) + 1
        if row["keyword"] != "unknown":
            keyword_counts[row["keyword"]] = keyword_counts.get(row["keyword"], 0) + 1

    expected_keywords = _load_expected_keywords()
    if not expected_keywords:
        expected_keywords = sorted(recent_keyword_dates.keys())
    inactive_keywords = []
    for keyword in expected_keywords:
        last_date = recent_keyword_dates.get(keyword)
        if last_date is None or last_date < stale_cutoff:
            inactive_keywords.append(
                {
                    "keyword": keyword,
                    "last_new_ad_date": last_date.isoformat() if last_date else None,
                    "days_since_new_ad": None if last_date is None else (target_date - last_date).days,
                }
            )
    inactive_keywords.sort(key=lambda item: (item["last_new_ad_date"] or "", item["keyword"]))

    daily_new_ads = len(new_rows)
    daily_unique_ads = len(unique_signatures)
    duplicate_rate = 0.0 if daily_new_ads == 0 else round((daily_new_ads - daily_unique_ads) / daily_new_ads, 4)
    stale_ad_rate = 0.0 if not rows else round(stale_count / len(rows), 4)

    return {
        "date": target_date.isoformat(),
        "daily_new_ads": daily_new_ads,
        "daily_unique_ads": daily_unique_ads,
        "duplicate_rate": duplicate_rate,
        "stale_ad_rate": stale_ad_rate,
        "platform_new_ad_counts": _sort_count_map(platform_counts),
        "advertiser_new_ad_counts": _sort_count_map(advertiser_counts),
        "keyword_new_ad_counts": _sort_count_map(keyword_counts),
        "inactive_keywords_7d": inactive_keywords[:25],
    }


def _sort_count_map(counts: dict[str, int]) -> list[dict]:
    rows = [{"label": label, "count": count} for label, count in counts.items()]
    rows.sort(key=lambda item: (-item["count"], item["label"]))
    return rows


def _new_ad_date_proxy(row: dict) -> date | None:
    for key in ("first_seen_at", "created_at"):
        parsed = _to_datetime(row.get(key))
        if parsed is not None:
            return parsed.date()
    return None


def _lp_score_value(meta: dict) -> float | int | None:
    value = meta.get("lp_score")
    if isinstance(value, dict):
        score = value.get("score")
        return score if isinstance(score, (int, float)) else None
    return value if isinstance(value, (int, float)) else None


def _extract_quality_value(meta: dict) -> float | int | None:
    value = meta.get("extract_quality_score")
    return value if isinstance(value, (int, float)) else None


def _numeric_value(ad: Ad, meta: dict, field: str) -> float | int | None:
    if field == "lp_score":
        return _lp_score_value(meta)
    if field == "extract_quality_score":
        return _extract_quality_value(meta)
    value = getattr(ad, field, None)
    return value if isinstance(value, (int, float)) else None


def _is_estimated_numeric(meta: dict, field: str) -> bool:
    method = _as_text(meta.get("estimation_method")).lower()
    metric_source = _normalize_label(meta.get("metric_source"))
    if field in {"lp_score", "extract_quality_score"}:
        return False
    if metric_source == "estimated":
        return field in {"spend", "impressions", "reach", "view_count"}
    if meta.get("metrics_estimated") is True:
        return field in {"spend", "impressions", "reach", "view_count"}
    if field == "spend" and (meta.get("estimated_spend_jpy") is not None or meta.get("estimated_cpm_jpy") is not None):
        return True
    if field in {"impressions", "view_count", "reach"} and meta.get("impressions_from_audience") is not None:
        return True
    return any(token in method for token in _ESTIMATED_METHOD_TOKENS)


def _numeric_updated_at(ad: Ad, meta: dict) -> datetime | None:
    return (
        _to_datetime(meta.get("metrics_collection_time"))
        or _to_datetime(meta.get("last_crawled_at"))
        or _to_datetime(meta.get("freshness_updated_at"))
        or _to_datetime(getattr(ad, "updated_at", None))
    )


def _init_numeric_bucket(label: str) -> dict:
    return {
        "label": label,
        "total_ads": 0,
        "fields": {
            field: {"real_count": 0, "estimated_count": 0, "missing_count": 0}
            for field in _NUMERIC_FIELDS
        },
        "estimated_only_count": 0,
        "missing_numeric_count": 0,
        "stale_real_metrics_count": 0,
    }


def _finalize_numeric_bucket(bucket: dict) -> dict:
    total = int(bucket["total_ads"] or 0)
    for field in _NUMERIC_FIELDS:
        counts = bucket["fields"][field]
        counts["real_rate"] = round(counts["real_count"] / total, 4) if total else 0.0
        counts["estimated_rate"] = round(counts["estimated_count"] / total, 4) if total else 0.0
        counts["missing_rate"] = round(counts["missing_count"] / total, 4) if total else 0.0
    bucket["estimated_only_rate"] = round(bucket["estimated_only_count"] / total, 4) if total else 0.0
    bucket["missing_numeric_rate"] = round(bucket["missing_numeric_count"] / total, 4) if total else 0.0
    bucket["stale_real_metrics_rate"] = round(bucket["stale_real_metrics_count"] / total, 4) if total else 0.0
    return bucket


def build_numeric_truth_audit(
    session: Session,
    *,
    target_date: date | None = None,
    top_n: int = _DEFAULT_TOP_N,
    previous: dict | None = None,
) -> dict:
    target_date = target_date or datetime.now(timezone.utc).date()
    stale_cutoff = target_date - timedelta(days=_STALE_WINDOW_DAYS)
    summary = _init_numeric_bucket("summary")
    platform_breakdown: dict[str, dict] = {}
    genre_breakdown: dict[str, dict] = {}
    ad_rows: list[dict] = []

    for ad in session.query(Ad).all():
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        numeric_states: dict[str, str] = {}
        real_count = 0
        estimated_count = 0
        missing_count = 0
        for field in _NUMERIC_FIELDS:
            value = _numeric_value(ad, meta, field)
            if value is None:
                state = "missing"
                missing_count += 1
            elif _is_estimated_numeric(meta, field):
                state = "estimated"
                estimated_count += 1
            else:
                state = "real"
                real_count += 1
            numeric_states[field] = state

        updated_at = _numeric_updated_at(ad, meta)
        stale_real = bool(real_count > 0 and updated_at and updated_at.date() < stale_cutoff)
        row = {
            "ad_id": ad.id,
            "title": ad.title or "",
            "platform": _platform_label(ad),
            "genre": _genre_label(ad),
            "advertiser": _advertiser_label(ad),
            "keyword": _keyword_label(ad),
            "numeric_states": numeric_states,
            "real_count": real_count,
            "estimated_count": estimated_count,
            "missing_count": missing_count,
            "estimated_only": real_count == 0 and estimated_count > 0,
            "missing_numeric": real_count == 0 and estimated_count == 0,
            "stale_real_metrics": stale_real,
            "last_numeric_at": updated_at.isoformat() if updated_at else None,
            "backfill_fields": [field for field, state in numeric_states.items() if state != "real"],
            "priority_score": round(
                _build_priority_score(
                    {
                        "updated_at": getattr(ad, "updated_at", None).isoformat() if getattr(ad, "updated_at", None) else None,
                        "spend": float(getattr(ad, "spend", 0.0) or 0.0),
                        "is_active": _is_active(ad, meta, target_date=target_date),
                        "failure_reason_codes": [field for field, state in numeric_states.items() if state != "real"],
                        "platform": _platform_label(ad),
                    },
                    target_date=target_date,
                ) + (8.0 if stale_real else 0.0),
                3,
            ),
        }
        ad_rows.append(row)

        for bucket in (
            summary,
            platform_breakdown.setdefault(row["platform"], _init_numeric_bucket(row["platform"])),
            genre_breakdown.setdefault(row["genre"], _init_numeric_bucket(row["genre"])),
        ):
            bucket["total_ads"] += 1
            for field, state in numeric_states.items():
                bucket["fields"][field][f"{state}_count"] += 1
            bucket["estimated_only_count"] += int(row["estimated_only"])
            bucket["missing_numeric_count"] += int(row["missing_numeric"])
            bucket["stale_real_metrics_count"] += int(row["stale_real_metrics"])

    summary = _finalize_numeric_bucket(summary)
    platform_rows = [_finalize_numeric_bucket(bucket) for bucket in platform_breakdown.values()]
    genre_rows = [_finalize_numeric_bucket(bucket) for bucket in genre_breakdown.values()]
    platform_rows.sort(key=lambda item: (-item["estimated_only_rate"], item["label"]))
    genre_rows.sort(key=lambda item: (-item["estimated_only_rate"], item["label"]))

    backfill_targets = [row for row in ad_rows if row["backfill_fields"]]
    backfill_targets.sort(key=lambda item: (-item["priority_score"], item["ad_id"]))

    previous_summary = None
    if isinstance(previous, dict):
        previous_summary = (previous.get("numeric_truth_audit") or {}).get("summary")

    return {
        "summary": {
            **summary,
            "estimated_only_count": summary["estimated_only_count"],
            "missing_numeric_count": summary["missing_numeric_count"],
            "stale_real_metrics_count": summary["stale_real_metrics_count"],
            "delta_vs_previous_day": _compute_delta(summary, previous_summary),
        },
        "platform_breakdown": platform_rows[:25],
        "genre_breakdown": genre_rows[:25],
        "priority_backfill_targets": backfill_targets[: max(1, top_n)],
        "ad_rows": ad_rows,
    }


def _normalize_language_tag(value: object) -> str | None:
    raw = _as_text(value).lower().replace("_", "-")
    if not raw:
        return None
    if raw in {"ja", "ja-jp", "jp", "japanese"} or raw.startswith("ja-"):
        return "ja"
    return raw


def _normalize_label(value: object) -> str:
    return _as_text(value).lower().replace(" ", "_")


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _contains_bedrock_source(*values: object) -> bool:
    for value in values:
        text = _as_text(value).lower()
        if text and any(token in text for token in _BEDROCK_SOURCE_TOKENS):
            return True
    return False


def _priority_bucket(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _actual_metrics_present(ad: Ad, meta: dict) -> bool:
    for field in ("spend", "impressions", "reach", "view_count"):
        value = _numeric_value(ad, meta, field)
        if value is not None and not _is_estimated_numeric(meta, field):
            return True
    return False


def _topic_reference_label(meta: dict) -> str:
    topic_tags = meta.get("topic_tags") if isinstance(meta.get("topic_tags"), list) else []
    for value in topic_tags:
        label = _normalize_label(value)
        if label:
            return label
    return ""


def _product_reference_label(ad: Ad, meta: dict) -> str:
    product_category = _normalize_label(meta.get("product_category"))
    if product_category:
        return product_category
    category = _normalize_label(getattr(getattr(ad, "category", None), "value", getattr(ad, "category", None)))
    if category and category != "unknown":
        return category
    topic = _normalize_label(meta.get("topic_label"))
    return topic


def _language_reference_label(ad: Ad, meta: dict) -> str:
    text = _ad_language_text(ad)
    ratio = float(meta.get("jp_char_ratio") or meta.get("japanese_ratio") or japanese_text_ratio(text) or 0.0)
    if ratio >= _JP_STRONG_THRESHOLD:
        return "ja"
    if ratio < _JP_WEAK_THRESHOLD:
        return "non_ja"
    return "unknown"


def _init_precision_metric(label: str) -> dict:
    return {
        "label": label,
        "evaluated_count": 0,
        "correct_count": 0,
        "mismatch_count": 0,
        "bedrock_used_count": 0,
        "accuracy_rate": 0.0,
    }


def _finalize_precision_metric(metric: dict) -> dict:
    total = int(metric["evaluated_count"] or 0)
    metric["accuracy_rate"] = round(metric["correct_count"] / total, 4) if total else 0.0
    metric["mismatch_rate"] = round(metric["mismatch_count"] / total, 4) if total else 0.0
    metric["bedrock_used_rate"] = round(metric["bedrock_used_count"] / total, 4) if total else 0.0
    return metric


def _bucket_row(label: str) -> dict:
    return {"label": label, "total_ads": 0, "with_real_metrics_count": 0, "with_real_metrics_rate": 0.0}


def _finalize_corr_bucket(bucket: dict) -> dict:
    total = int(bucket["total_ads"] or 0)
    bucket["with_real_metrics_rate"] = round(bucket["with_real_metrics_count"] / total, 4) if total else 0.0
    return bucket


def build_bedrock_precision_roi_audit(
    session: Session,
    *,
    target_date: date | None = None,
    top_n: int = _DEFAULT_TOP_N,
) -> dict:
    target_date = target_date or datetime.now(timezone.utc).date()
    summary = {
        "total_ads": 0,
        "rule_only_count": 0,
        "bedrock_used_count": 0,
        "manual_review_count": 0,
        "review_required_count": 0,
        "bedrock_valuable_count": 0,
    }
    precision = {
        "language": _init_precision_metric("language"),
        "product_category": _init_precision_metric("product_category"),
        "topic_label": _init_precision_metric("topic_label"),
        "priority_score": _init_precision_metric("priority_score"),
    }
    false_positive: dict[str, dict] = {}
    false_negative: dict[str, dict] = {}
    manual_review_queue: list[dict] = []
    top_priority_missing_real_metrics: list[dict] = []
    priority_buckets = {
        "high": _bucket_row("high"),
        "medium": _bucket_row("medium"),
        "low": _bucket_row("low"),
    }
    priority_with_real_metrics: list[float] = []
    priority_without_real_metrics: list[float] = []

    review_required_policy = {
        "send_if": [
            "explicit review_required/manual_review flag is set",
            "bedrock prediction disagrees with rule or taxonomy proxy at high confidence",
            "high-priority ad is missing language/product/topic labeling",
            "high-priority ad has low extract_quality_score or low topic_confidence",
        ]
    }
    bedrock_value_policy = {
        "call_if": [
            "ad is high priority and rule-only signals are missing or ambiguous",
            "language detection is ambiguous or disagrees with Japanese ratio proxy",
            "product/topic labels are missing on active ads with spend or actual metrics",
            "high-value ad needs review because confidence is low or labels conflict",
        ],
        "skip_if": [
            "rule-only signals are consistent and confidence is already sufficient",
            "ad is low priority and no ambiguity/mismatch is present",
        ],
    }

    for ad in session.query(Ad).all():
        summary["total_ads"] += 1
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}

        language = _normalize_language_tag(meta.get("language")) or ""
        language_reference = _language_reference_label(ad, meta)
        language_bedrock = _contains_bedrock_source(meta.get("language_source"), meta.get("classification_source"))
        language_conf = _coerce_float(meta.get("language_confidence") or meta.get("classification_confidence"))

        product_category = _normalize_label(meta.get("product_category") or meta.get("product_name"))
        product_reference = _normalize_label(getattr(getattr(ad, "category", None), "value", getattr(ad, "category", None)))
        product_bedrock = _contains_bedrock_source(meta.get("product_category_source"), meta.get("classification_source"))
        product_conf = _coerce_float(meta.get("product_category_confidence") or meta.get("classification_confidence"))

        topic_label = _normalize_label(meta.get("topic_label"))
        topic_reference = _topic_reference_label(meta)
        topic_bedrock = _contains_bedrock_source(meta.get("topic_source"), meta.get("classification_source"))
        topic_conf = _coerce_float(meta.get("topic_confidence") or meta.get("classification_confidence"))

        computed_priority = _build_priority_score(
            {
                "updated_at": getattr(ad, "updated_at", None).isoformat() if getattr(ad, "updated_at", None) else None,
                "spend": float(getattr(ad, "spend", 0.0) or 0.0),
                "is_active": _is_active(ad, meta, target_date=target_date),
                "failure_reason_codes": [
                    code
                    for code, present in (
                        ("missing_language", bool(language)),
                        ("missing_product", bool(product_category)),
                        ("missing_topic", bool(topic_label)),
                    )
                    if not present
                ],
                "platform": _platform_label(ad),
            },
            target_date=target_date,
        )
        stored_priority = _coerce_float(meta.get("priority_score") or meta.get("ranking_priority_score"), computed_priority)
        actual_metrics_present = _actual_metrics_present(ad, meta)
        language_mismatch = bool(language) and language_reference != "unknown" and not (
            (language == "ja" and language_reference == "ja") or (language != "ja" and language_reference == "non_ja")
        )
        product_mismatch = bool(product_category) and bool(product_reference) and product_category != product_reference
        topic_mismatch = bool(topic_label) and bool(topic_reference) and topic_label != topic_reference

        precision["language"]["evaluated_count"] += int(bool(language) and language_reference != "unknown")
        if language and language_reference != "unknown":
            precision["language"]["bedrock_used_count"] += int(language_bedrock)
            if not language_mismatch:
                precision["language"]["correct_count"] += 1
            else:
                precision["language"]["mismatch_count"] += 1

        precision["product_category"]["evaluated_count"] += int(bool(product_category) and bool(product_reference))
        if product_category and product_reference:
            precision["product_category"]["bedrock_used_count"] += int(product_bedrock)
            if not product_mismatch:
                precision["product_category"]["correct_count"] += 1
            else:
                precision["product_category"]["mismatch_count"] += 1

        precision["topic_label"]["evaluated_count"] += int(bool(topic_label) and bool(topic_reference))
        if topic_label and topic_reference:
            precision["topic_label"]["bedrock_used_count"] += int(topic_bedrock)
            if not topic_mismatch:
                precision["topic_label"]["correct_count"] += 1
            else:
                precision["topic_label"]["mismatch_count"] += 1

        precision["priority_score"]["evaluated_count"] += 1
        precision["priority_score"]["bedrock_used_count"] += int(
            _contains_bedrock_source(meta.get("priority_score_source"), meta.get("classification_source"))
        )
        if _priority_bucket(stored_priority) == _priority_bucket(computed_priority):
            precision["priority_score"]["correct_count"] += 1
        else:
            precision["priority_score"]["mismatch_count"] += 1

        label_missing = any(not value for value in (language, product_category, topic_label))
        low_extract_quality = _coerce_float(meta.get("extract_quality_score")) < 40.0 and meta.get("extract_quality_score") is not None
        low_topic_confidence = 0.0 < topic_conf < 0.6
        explicit_review = bool(meta.get("review_required") or meta.get("manual_review") or meta.get("needs_topic_review"))
        mismatch_high_confidence = any(
            (
                language_bedrock and language_mismatch and language_conf >= _HIGH_CONFIDENCE_THRESHOLD,
                product_bedrock and product_mismatch and product_conf >= _HIGH_CONFIDENCE_THRESHOLD,
                topic_bedrock and topic_mismatch and topic_conf >= _HIGH_CONFIDENCE_THRESHOLD,
            )
        )
        review_required = explicit_review or mismatch_high_confidence or (
            stored_priority >= _HIGH_PRIORITY_THRESHOLD and (label_missing or low_extract_quality or low_topic_confidence)
        )

        valuable_for_bedrock = (
            stored_priority >= _HIGH_PRIORITY_THRESHOLD
            and (
                label_missing
                or language_reference == "unknown"
                or low_extract_quality
                or low_topic_confidence
                or not actual_metrics_present
            )
        )

        if review_required:
            summary["manual_review_count"] += 1
        elif language_bedrock or product_bedrock or topic_bedrock:
            summary["bedrock_used_count"] += 1
        else:
            summary["rule_only_count"] += 1

        summary["review_required_count"] += int(review_required)
        summary["bedrock_valuable_count"] += int(valuable_for_bedrock)

        if actual_metrics_present:
            priority_with_real_metrics.append(stored_priority)
        else:
            priority_without_real_metrics.append(stored_priority)
            top_priority_missing_real_metrics.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "platform": _platform_label(ad),
                    "priority_score": round(stored_priority, 3),
                }
            )
        bucket = priority_buckets[_priority_bucket(stored_priority)]
        bucket["total_ads"] += 1
        bucket["with_real_metrics_count"] += int(actual_metrics_present)

        if review_required and len(manual_review_queue) < top_n:
            manual_review_queue.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "platform": _platform_label(ad),
                    "priority_score": round(stored_priority, 3),
                    "language": language or None,
                    "product_category": product_category or None,
                    "topic_label": topic_label or None,
                    "actual_metrics_present": actual_metrics_present,
                }
            )

        predicted_product = product_category or topic_label or _product_reference_label(ad, meta) or "unknown"
        reference_product = product_reference or topic_reference or _product_reference_label(ad, meta) or "unknown"
        if mismatch_high_confidence and predicted_product != reference_product:
            fp_bucket = false_positive.setdefault(predicted_product, {"product_category": predicted_product, "count": 0, "sample_ad_ids": []})
            fp_bucket["count"] += 1
            if len(fp_bucket["sample_ad_ids"]) < 5:
                fp_bucket["sample_ad_ids"].append(ad.id)
            fn_bucket = false_negative.setdefault(reference_product, {"product_category": reference_product, "count": 0, "sample_ad_ids": []})
            fn_bucket["count"] += 1
            if len(fn_bucket["sample_ad_ids"]) < 5:
                fn_bucket["sample_ad_ids"].append(ad.id)

    total = summary["total_ads"] or 1
    for key in ("rule_only_count", "bedrock_used_count", "manual_review_count", "review_required_count", "bedrock_valuable_count"):
        rate_key = key.replace("_count", "_rate")
        summary[rate_key] = round(summary[key] / total, 4)

    precision = {label: _finalize_precision_metric(metric) for label, metric in precision.items()}
    top_priority_missing_real_metrics.sort(key=lambda row: (-row["priority_score"], row["ad_id"]))

    fp_rows = list(false_positive.values())
    fn_rows = list(false_negative.values())
    fp_rows.sort(key=lambda row: (-row["count"], row["product_category"]))
    fn_rows.sort(key=lambda row: (-row["count"], row["product_category"]))
    corr_rows = [_finalize_corr_bucket(bucket) for bucket in priority_buckets.values()]
    corr_rows.sort(key=lambda row: {"high": 0, "medium": 1, "low": 2}[row["label"]])

    return {
        "summary": summary,
        "accuracy_proxy": precision,
        "by_product_false_positives": fp_rows[: max(1, top_n)],
        "by_product_false_negatives": fn_rows[: max(1, top_n)],
        "manual_review_queue": manual_review_queue,
        "review_required_policy": review_required_policy,
        "bedrock_value_policy": bedrock_value_policy,
        "priority_score_roi": {
            "avg_priority_with_actual_metrics": round(sum(priority_with_real_metrics) / len(priority_with_real_metrics), 3)
            if priority_with_real_metrics
            else 0.0,
            "avg_priority_without_actual_metrics": round(sum(priority_without_real_metrics) / len(priority_without_real_metrics), 3)
            if priority_without_real_metrics
            else 0.0,
            "real_metrics_capture_by_priority_bucket": corr_rows,
            "top_priority_missing_real_metrics": top_priority_missing_real_metrics[: max(1, top_n)],
        },
    }


def _is_meta_ad(ad: Ad, meta: dict) -> bool:
    platform = _platform_label(ad)
    if platform in _META_PLATFORMS:
        return True
    publisher_platforms = meta.get("publisher_platforms") if isinstance(meta.get("publisher_platforms"), list) else []
    return any(_normalize_label(value) in _META_PLATFORMS for value in publisher_platforms)


def _has_real_numeric_metrics(ad: Ad, meta: dict) -> bool:
    for field in ("spend", "impressions", "reach", "view_count"):
        value = _numeric_value(ad, meta, field)
        if value not in (None, 0, 0.0) and not _is_estimated_numeric(meta, field):
            return True
    return False


def _has_estimated_numeric_metrics(ad: Ad, meta: dict) -> bool:
    for field in ("spend", "impressions", "reach", "view_count"):
        value = _numeric_value(ad, meta, field)
        if value not in (None, 0, 0.0) and _is_estimated_numeric(meta, field):
            return True
    return False


def _meta_new_saved(ad: Ad, *, target_date: date) -> bool:
    created = _to_datetime(getattr(ad, "created_at", None))
    first_seen = _to_datetime(getattr(ad, "first_seen_at", None))
    return any(candidate and candidate.date() == target_date for candidate in (created, first_seen))


def _meta_api_failure(meta: dict) -> bool:
    joined = " ".join(
        _as_text(meta.get(key)).lower()
        for key in (
            "snapshot_fallback_reason",
            "creative_fetch_reason",
            "lp_fetch_error_code",
            "media_extraction_status",
        )
    )
    return any(token in joined for token in ("api", "http_error", "non_200", "failed", "rate_limit", "render_ad_http_error"))


def _meta_token_expired(meta: dict) -> bool:
    joined = " ".join(_as_text(meta.get(key)).lower() for key in ("snapshot_fallback_reason", "creative_fetch_reason", "lp_fetch_error_code"))
    return any(token in joined for token in ("token_expired", "oauth", "access token"))


def _meta_browser_fallback(meta: dict) -> bool:
    return any(
        _normalize_label(meta.get(key)) in {"browser_scraping", "browser_overlay", "playwright_render_ad"}
        for key in ("source", "crawl_source", "creative_fetch_source")
    ) or bool(_as_text(meta.get("snapshot_fallback_reason")))


def build_meta_completion_audit(
    session: Session,
    *,
    target_date: date | None = None,
    top_n: int = _DEFAULT_TOP_N,
) -> dict:
    target_date = target_date or datetime.now(timezone.utc).date()
    summary = {
        "total_meta_ads": 0,
        "real_metrics_count": 0,
        "estimated_metrics_count": 0,
        "missing_metrics_count": 0,
        "jp_count": 0,
        "new_saved_count": 0,
        "lp_attached_count": 0,
        "creative_attached_count": 0,
        "saved_without_real_metrics_count": 0,
        "token_valid_but_api_failed_count": 0,
        "browser_fallback_dependency_count": 0,
    }
    field_states = {
        field: {"real_count": 0, "estimated_count": 0, "missing_count": 0}
        for field in ("spend", "impressions", "reach", "view_count")
    }
    saved_without_real_metrics: list[dict] = []
    api_failure_samples: list[dict] = []
    browser_fallback_samples: list[dict] = []

    acceptance_policy = {
        "accepted_80_if": [
            "completion_score >= 80",
            "real_metrics_rate >= 0.50",
            "lp_attach_rate >= 0.70",
            "creative_attach_rate >= 0.80",
        ],
        "accepted_90_if": [
            "completion_score >= 90",
            "real_metrics_rate >= 0.70",
            "browser_fallback_dependency_rate <= 0.20",
            "token_valid_but_api_failed_rate <= 0.05",
        ],
    }

    for ad in session.query(Ad).all():
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        if not _is_meta_ad(ad, meta):
            continue

        summary["total_meta_ads"] += 1
        has_real_metrics = _has_real_numeric_metrics(ad, meta)
        has_estimated_metrics = _has_estimated_numeric_metrics(ad, meta)
        jp_ratio = float(meta.get("jp_char_ratio") or meta.get("japanese_ratio") or japanese_text_ratio(_ad_language_text(ad)) or 0.0)
        is_new_saved = _meta_new_saved(ad, target_date=target_date)
        has_lp = _has_lp_present(ad, meta)
        has_creative = bool(ad.thumbnail_url or ad.image_url or ad.video_url or ad.thumbnail_s3_key or ad.image_s3_key or ad.s3_key)
        api_failure = _meta_api_failure(meta) and not _meta_token_expired(meta)
        browser_fallback = _meta_browser_fallback(meta)

        if has_real_metrics:
            summary["real_metrics_count"] += 1
        elif has_estimated_metrics:
            summary["estimated_metrics_count"] += 1
        else:
            summary["missing_metrics_count"] += 1

        summary["jp_count"] += int(jp_ratio >= _JP_STRONG_THRESHOLD)
        summary["new_saved_count"] += int(is_new_saved)
        summary["lp_attached_count"] += int(has_lp)
        summary["creative_attached_count"] += int(has_creative)
        summary["token_valid_but_api_failed_count"] += int(api_failure)
        summary["browser_fallback_dependency_count"] += int(browser_fallback)

        save_signal = is_new_saved or int(_coerce_float(meta.get("crawl_result_count")))
        if save_signal and not has_real_metrics:
            summary["saved_without_real_metrics_count"] += 1
            if len(saved_without_real_metrics) < top_n:
                saved_without_real_metrics.append(
                    {
                        "ad_id": ad.id,
                        "title": ad.title or "",
                        "platform": _platform_label(ad),
                        "saved_signal": "new_saved" if is_new_saved else "crawl_result_count",
                        "crawl_result_count": int(_coerce_float(meta.get("crawl_result_count"))),
                        "metrics_state": "estimated" if has_estimated_metrics else "missing",
                    }
                )

        if api_failure and len(api_failure_samples) < top_n:
            api_failure_samples.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "platform": _platform_label(ad),
                    "reason": _as_text(meta.get("snapshot_fallback_reason") or meta.get("creative_fetch_reason") or meta.get("lp_fetch_error_code")) or None,
                }
            )
        if browser_fallback and len(browser_fallback_samples) < top_n:
            browser_fallback_samples.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "platform": _platform_label(ad),
                    "source": _as_text(meta.get("source") or meta.get("crawl_source") or meta.get("creative_fetch_source")) or None,
                }
            )

        for field in field_states:
            value = _numeric_value(ad, meta, field)
            if value is None:
                state = "missing"
            elif _is_estimated_numeric(meta, field):
                state = "estimated"
            else:
                state = "real"
            field_states[field][f"{state}_count"] += 1

    total = summary["total_meta_ads"] or 1
    for key in list(summary.keys()):
        if key.endswith("_count") and key != "total_meta_ads":
            summary[key.replace("_count", "_rate")] = round(summary[key] / total, 4)

    for field, counts in field_states.items():
        counts["real_rate"] = round(counts["real_count"] / total, 4)
        counts["estimated_rate"] = round(counts["estimated_count"] / total, 4)
        counts["missing_rate"] = round(counts["missing_count"] / total, 4)

    completion_components = [
        summary["real_metrics_rate"],
        summary["lp_attached_rate"],
        summary["creative_attached_rate"],
        1.0 - summary["browser_fallback_dependency_rate"],
        1.0 - summary["token_valid_but_api_failed_rate"],
    ]
    completion_score = round((sum(completion_components) / len(completion_components)) * 100, 1)

    return {
        "summary": {
            **summary,
            "numeric_mix": field_states,
            "completion_score": completion_score,
            "accepted_80": completion_score >= 80.0 and summary["real_metrics_rate"] >= 0.5 and summary["lp_attached_rate"] >= 0.7 and summary["creative_attached_rate"] >= 0.8,
            "accepted_90": completion_score >= 90.0 and summary["real_metrics_rate"] >= 0.7 and summary["browser_fallback_dependency_rate"] <= 0.2 and summary["token_valid_but_api_failed_rate"] <= 0.05,
        },
        "saved_without_real_metrics": saved_without_real_metrics,
        "api_failure_samples": api_failure_samples,
        "browser_fallback_samples": browser_fallback_samples,
        "acceptance_policy": acceptance_policy,
    }


def _ad_language_text(ad: Ad) -> str:
    return " ".join(
        filter(
            None,
            [
                ad.title,
                ad.description,
                ad.advertiser_name,
                ad.brand_name,
            ],
        )
    )


def build_japanese_inventory_audit(
    session: Session,
    *,
    target_date: date | None = None,
    top_n: int = _DEFAULT_TOP_N,
) -> dict:
    _ = target_date
    summary = {
        "total_ads": 0,
        "jp_count": 0,
        "non_jp_count": 0,
        "unknown_count": 0,
        "excluded_count": 0,
        "manual_review_count": 0,
        "coverage": {
            "jp_char_ratio": 0,
            "language_source": 0,
            "exclude_from_analysis": 0,
            "exclude_reason": 0,
        },
    }
    mismatch_samples: list[dict] = []
    manual_review_queue: list[dict] = []
    platform_breakdown: dict[str, dict] = {}

    exclusion_policy = {
        "exclude_if": [
            "language_tag is explicitly non-ja",
            f"jp_char_ratio < {_JP_WEAK_THRESHOLD:.2f} and no positive Japanese language signal",
        ],
        "manual_review_if": [
            f"{_JP_WEAK_THRESHOLD:.2f} <= jp_char_ratio < {_JP_STRONG_THRESHOLD:.2f}",
            "language metadata disagrees with rule-based detection",
            "exclude_from_analysis is unset and language status is unknown",
        ],
    }

    for ad in session.query(Ad).all():
        summary["total_ads"] += 1
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        platform = _platform_label(ad)
        bucket = platform_breakdown.setdefault(
            platform,
            {"label": platform, "total_ads": 0, "jp_count": 0, "non_jp_count": 0, "unknown_count": 0, "excluded_count": 0},
        )
        bucket["total_ads"] += 1

        text = _ad_language_text(ad)
        ratio = float(meta.get("jp_char_ratio") or meta.get("japanese_ratio") or japanese_text_ratio(text) or 0.0)
        language_tag = _normalize_language_tag(meta.get("language"))
        language_source = _as_text(meta.get("language_source"))
        rule_based_label = "jp" if ratio >= _JP_STRONG_THRESHOLD else "non_jp" if ratio < _JP_WEAK_THRESHOLD else "unknown"
        if language_tag == "ja":
            inventory_label = "jp"
        elif language_tag and language_tag != "ja":
            inventory_label = "non_jp"
        else:
            inventory_label = rule_based_label

        if inventory_label == "jp":
            summary["jp_count"] += 1
            bucket["jp_count"] += 1
        elif inventory_label == "non_jp":
            summary["non_jp_count"] += 1
            bucket["non_jp_count"] += 1
        else:
            summary["unknown_count"] += 1
            bucket["unknown_count"] += 1

        if meta.get("jp_char_ratio") is not None or meta.get("japanese_ratio") is not None:
            summary["coverage"]["jp_char_ratio"] += 1
        if language_source:
            summary["coverage"]["language_source"] += 1
        if "exclude_from_analysis" in meta:
            summary["coverage"]["exclude_from_analysis"] += 1
        if _as_text(meta.get("exclude_reason")):
            summary["coverage"]["exclude_reason"] += 1

        exclude_reason = _as_text(meta.get("exclude_reason"))
        excluded = bool(meta.get("exclude_from_analysis"))
        if excluded:
            summary["excluded_count"] += 1
            bucket["excluded_count"] += 1

        ai_language_available = bool(language_source and any(token in language_source.lower() for token in ("bedrock", "ai", "comprehend")))
        mismatch = ai_language_available and language_tag is not None and (
            (language_tag == "ja" and rule_based_label == "non_jp")
            or (language_tag != "ja" and rule_based_label == "jp")
        )
        if mismatch and len(mismatch_samples) < top_n:
            mismatch_samples.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "platform": platform,
                    "language": language_tag,
                    "language_source": language_source,
                    "rule_based_label": rule_based_label,
                    "jp_char_ratio": round(ratio, 4),
                }
            )

        needs_manual_review = mismatch or (_JP_WEAK_THRESHOLD <= ratio < _JP_STRONG_THRESHOLD) or (inventory_label == "unknown" and not excluded)
        if needs_manual_review:
            summary["manual_review_count"] += 1
            if len(manual_review_queue) < top_n:
                manual_review_queue.append(
                    {
                        "ad_id": ad.id,
                        "title": ad.title or "",
                        "platform": platform,
                        "inventory_label": inventory_label,
                        "jp_char_ratio": round(ratio, 4),
                        "language": language_tag,
                        "language_source": language_source or None,
                        "exclude_from_analysis": excluded,
                        "exclude_reason": exclude_reason or None,
                    }
                )

    total = summary["total_ads"] or 1
    summary["jp_rate"] = round(summary["jp_count"] / total, 4)
    summary["non_jp_rate"] = round(summary["non_jp_count"] / total, 4)
    summary["unknown_rate"] = round(summary["unknown_count"] / total, 4)
    for key, value in list(summary["coverage"].items()):
        summary["coverage"][key] = {"count": value, "rate": round(value / total, 4)}

    platform_rows = list(platform_breakdown.values())
    platform_rows.sort(key=lambda item: (-item["non_jp_count"], item["label"]))

    return {
        "summary": summary,
        "platform_breakdown": platform_rows[:25],
        "bedrock_rule_mismatch_samples": mismatch_samples,
        "manual_review_queue": manual_review_queue,
        "exclusion_policy": exclusion_policy,
    }


def build_creative_library_audit(
    session: Session,
    *,
    target_date: date | None = None,
    top_n: int = _DEFAULT_TOP_N,
    persist: bool = True,
) -> dict:
    """Build a creative library audit report consumable by planners/dashboards."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    ads = session.query(Ad).all()
    platform_breakdown: dict[str, dict] = {}
    genre_breakdown: dict[str, dict] = {}
    advertiser_breakdown: dict[str, dict] = {}
    rows: list[dict] = []

    summary = _empty_bucket("summary")
    failure_reason_counts = {
        "missing_creative": 0,
        "not_downloadable": 0,
        "missing_lp": 0,
        "lp_unresolved": 0,
        "stale_snapshot": 0,
    }

    for ad in ads:
        row = _build_ad_audit_row(ad, target_date=target_date)
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        row["created_at"] = ad.created_at.isoformat() if getattr(ad, "created_at", None) else None
        row["freshness_score"] = meta.get("freshness_score")
        rows.append(row)

        _accumulate_bucket(summary, row)
        for code in row["failure_reason_codes"]:
            failure_reason_counts[code] = failure_reason_counts.get(code, 0) + 1

        for collection, label in (
            (platform_breakdown, row["platform"]),
            (genre_breakdown, row["genre"]),
            (advertiser_breakdown, row["advertiser"]),
        ):
            bucket = collection.setdefault(label, _empty_bucket(label))
            _accumulate_bucket(bucket, row)

    summary = _finalize_bucket(summary)
    platform_rows = _bucket_labels(25, platform_breakdown)
    genre_rows = _bucket_labels(25, genre_breakdown)
    advertiser_rows = _bucket_labels(25, advertiser_breakdown)

    recovery_candidates = [row for row in rows if row["failure_reason_codes"]]
    recovery_candidates.sort(key=lambda item: (-item["priority_score"], item["ad_id"]))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": target_date.isoformat(),
        "summary": summary,
        "platform_breakdown": platform_rows,
        "genre_breakdown": genre_rows,
        "advertiser_breakdown": advertiser_rows,
        "failure_reason_counts": failure_reason_counts,
        "priority_recovery_ads": recovery_candidates[: max(1, top_n)],
        "creative_library_gap_audit": {
            "summary": {
                "creative_viewable_rate": summary["creative_viewable_rate"],
                "creative_downloadable_rate": summary["creative_downloadable_rate"],
                "lp_present_rate": summary["lp_present_rate"],
                "lp_resolved_rate": summary["lp_resolved_rate"],
            },
            "failure_reason_counts": failure_reason_counts,
            "priority_recovery_ads": recovery_candidates[: max(1, top_n)],
        },
        "deltas": {},
        "ad_rows": rows,
    }

    history = _load_history()
    previous = history[-1] if history else None

    report["deltas"] = {
        "summary": _compute_delta(report["summary"], previous.get("summary") if isinstance(previous, dict) else None),
        "platform_breakdown": _compute_breakdown_deltas(
            report["platform_breakdown"],
            previous.get("platform_breakdown") if isinstance(previous, dict) else None,
        ),
        "genre_breakdown": _compute_breakdown_deltas(
            report["genre_breakdown"],
            previous.get("genre_breakdown") if isinstance(previous, dict) else None,
        ),
        "advertiser_breakdown": _compute_breakdown_deltas(
            report["advertiser_breakdown"],
            previous.get("advertiser_breakdown") if isinstance(previous, dict) else None,
        ),
    }
    report["creative_library_daily_report"] = _build_daily_report(rows, previous)
    report["creative_library_daily_report"]["worsening_segments"] = (
        _segment_worsening("platform", report["platform_breakdown"], previous.get("platform_breakdown") if isinstance(previous, dict) else None)[:10]
        + _segment_worsening("advertiser", report["advertiser_breakdown"], previous.get("advertiser_breakdown") if isinstance(previous, dict) else None)[:10]
        + _segment_worsening("genre", report["genre_breakdown"], previous.get("genre_breakdown") if isinstance(previous, dict) else None)[:10]
    )[:20]
    report["live_ingestion_audit"] = _build_live_ingestion_audit(rows, target_date=target_date)
    report["slo_status"], report["ops_alert_candidates"] = _build_ops_alerts(report, previous)
    report["numeric_truth_audit"] = build_numeric_truth_audit(
        session,
        target_date=target_date,
        top_n=top_n,
        previous=previous,
    )
    report["japanese_inventory_audit"] = build_japanese_inventory_audit(
        session,
        target_date=target_date,
        top_n=top_n,
    )
    report["bedrock_precision_roi_audit"] = build_bedrock_precision_roi_audit(
        session,
        target_date=target_date,
        top_n=top_n,
    )
    report["meta_completion_audit"] = build_meta_completion_audit(
        session,
        target_date=target_date,
        top_n=top_n,
    )

    if persist:
        _persist_report(report)

    return {
        "creative_library_audit": report,
    }
