"""Continuous crawl + knowledge pipeline helpers for Agent A."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.models.ad import Ad

BASE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
KNOWLEDGE_BASE_FILE = BASE_DATA_DIR / "topic_knowledge_base.json"
KNOWLEDGE_RUNS_FILE = BASE_DATA_DIR / "crawl_knowledge_runs.json"


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _save_json_list(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def build_topic_knowledge_rows(ads: list[Ad], *, updated_at: str | None = None) -> list[dict]:
    now_iso = updated_at or datetime.now(timezone.utc).isoformat()
    rows_by_topic: dict[str, dict] = {}

    for ad in ads:
        meta = ad.ad_metadata or {}
        topic_tags = _coerce_list(meta.get("topic_tags"))
        if not topic_tags:
            topic_label = str(meta.get("topic_label") or "").strip()
            if topic_label:
                topic_tags = [topic_label]
        evidence_terms = _coerce_list(meta.get("topic_evidence")) or _coerce_list(meta.get("matched_terms"))
        hit_drivers = _coerce_list(meta.get("hit_drivers"))

        for topic in topic_tags:
            bucket = rows_by_topic.setdefault(
                topic,
                {
                    "topic": topic,
                    "evidence_terms": [],
                    "hit_drivers": [],
                    "source_ad_ids": [],
                    "updated_at": now_iso,
                },
            )
            for term in evidence_terms:
                if term not in bucket["evidence_terms"]:
                    bucket["evidence_terms"].append(term)
            for driver in hit_drivers:
                if driver not in bucket["hit_drivers"]:
                    bucket["hit_drivers"].append(driver)
            if ad.id not in bucket["source_ad_ids"]:
                bucket["source_ad_ids"].append(ad.id)
            bucket["updated_at"] = now_iso

    rows = list(rows_by_topic.values())
    rows.sort(key=lambda row: (len(row["source_ad_ids"]), row["topic"]), reverse=True)
    for row in rows:
        row["evidence_terms"] = row["evidence_terms"][:20]
        row["hit_drivers"] = row["hit_drivers"][:12]
        row["source_ad_ids"] = row["source_ad_ids"][:50]
    return rows


def persist_crawl_knowledge_snapshot(
    ads: list[Ad],
    *,
    source: str,
    trigger_job_id: str | None = None,
    query: str | None = None,
    schedule_window: str | None = None,
    priority: str = "normal",
) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    knowledge_rows = build_topic_knowledge_rows(ads, updated_at=now_iso)

    knowledge_base = {row.get("topic"): row for row in _load_json_list(KNOWLEDGE_BASE_FILE)}
    for row in knowledge_rows:
        topic = str(row.get("topic") or "").strip()
        if not topic:
            continue
        existing = knowledge_base.get(topic) or {
            "topic": topic,
            "evidence_terms": [],
            "hit_drivers": [],
            "source_ad_ids": [],
            "updated_at": now_iso,
        }
        for key, limit in (("evidence_terms", 30), ("hit_drivers", 20), ("source_ad_ids", 100)):
            merged = list(existing.get(key) or [])
            for value in row.get(key) or []:
                if value not in merged:
                    merged.append(value)
            existing[key] = merged[:limit]
        existing["updated_at"] = now_iso
        knowledge_base[topic] = existing

    next_base = sorted(knowledge_base.values(), key=lambda row: row.get("topic", ""))
    _save_json_list(KNOWLEDGE_BASE_FILE, next_base)

    evidence_counter = Counter()
    driver_counter = Counter()
    for row in knowledge_rows:
        evidence_counter.update(_coerce_list(row.get("evidence_terms")))
        driver_counter.update(_coerce_list(row.get("hit_drivers")))

    snapshot = {
        "created_at": now_iso,
        "source": str(source or "manual").strip().lower() or "manual",
        "trigger_job_id": trigger_job_id,
        "query": str(query or "").strip(),
        "schedule_window": str(schedule_window or "").strip().lower() or None,
        "priority": str(priority or "normal").strip().lower() or "normal",
        "scanned_ads": len(ads),
        "knowledge_rows": knowledge_rows,
        "dictionary_candidate_summary": {
            "new_evidence_terms": [
                {"term": term, "count": count}
                for term, count in evidence_counter.most_common(10)
            ],
            "strong_hit_drivers": [
                {"driver": driver, "count": count}
                for driver, count in driver_counter.most_common(10)
            ],
        },
    }

    runs = _load_json_list(KNOWLEDGE_RUNS_FILE)
    runs.append(snapshot)
    _save_json_list(KNOWLEDGE_RUNS_FILE, runs[-200:])
    return snapshot
