#!/usr/bin/env python3
"""Run daily priority quick-crawl jobs for Meta (Facebook/Instagram).

Selects high-priority queries from:
1) learned recovery dictionary success history
2) static JP-market high-volume vertical terms

Then dispatches `/api/v1/rankings/quick-crawl` for each query.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "platform_query_learnings.json"
EXPORT_DIR = BASE_DIR / "exports"

DEFAULT_STATIC_QUERIES = [
    "GLP-1",
    "医療ダイエット",
    "AGA治療",
    "医療脱毛",
    "美容クリニック",
    "転職",
    "資産運用",
]


def _load_learning_data() -> dict:
    if not DATA_FILE.exists():
        return {"platforms": {}}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"platforms": {}}


def _select_priority_queries(learning_data: dict, limit: int) -> list[str]:
    platforms = learning_data.get("platforms") if isinstance(learning_data, dict) else {}
    if not isinstance(platforms, dict):
        platforms = {}

    scored: dict[str, float] = {}
    for p in ("facebook", "instagram"):
        p_map = platforms.get(p) if isinstance(platforms.get(p), dict) else {}
        for base_query, rec_map in p_map.items():
            if not isinstance(rec_map, dict):
                continue
            success_total = 0
            attempts_total = 0
            for stats in rec_map.values():
                if not isinstance(stats, dict):
                    continue
                success_total += int(stats.get("success") or 0)
                attempts_total += int(stats.get("attempts") or 0)
            if attempts_total <= 0:
                continue
            score = success_total + (success_total / attempts_total)
            key = str(base_query or "").strip()
            if not key:
                continue
            scored[key] = max(scored.get(key, 0.0), float(score))

    learned_ranked = [q for q, _ in sorted(scored.items(), key=lambda x: x[1], reverse=True)]
    merged: list[str] = []
    for q in learned_ranked + DEFAULT_STATIC_QUERIES:
        nq = str(q or "").strip()
        if not nq:
            continue
        if nq not in merged:
            merged.append(nq)
    return merged[: max(1, limit)]


def main():
    parser = argparse.ArgumentParser(description="Run daily Meta/Instagram priority quick-crawl jobs")
    parser.add_argument("--api-base", default=os.getenv("VAAP_API_BASE", "http://localhost:8000/api/v1"))
    parser.add_argument("--query-limit", type=int, default=8)
    parser.add_argument("--crawl-limit", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    learning_data = _load_learning_data()
    queries = _select_priority_queries(learning_data, limit=max(1, int(args.query_limit)))

    started_at = datetime.now(timezone.utc)
    report = {
        "started_at": started_at.isoformat(),
        "api_base": args.api_base,
        "query_count": len(queries),
        "queries": queries,
        "results": [],
    }

    if args.dry_run:
        report["status"] = "dry_run"
    else:
        endpoint = f"{args.api_base.rstrip('/')}/rankings/quick-crawl"
        for q in queries:
            payload = {
                "query": q,
                "platforms": ["facebook", "instagram"],
                "limit": max(1, int(args.crawl_limit)),
                "country": "JP",
            }
            row = {"query": q, "ok": False}
            try:
                resp = requests.post(endpoint, json=payload, timeout=max(30, int(args.timeout)))
                row["status_code"] = resp.status_code
                if resp.headers.get("content-type", "").startswith("application/json"):
                    data = resp.json()
                else:
                    data = {"raw": resp.text[:500]}
                row["response"] = data
                row["ok"] = resp.status_code < 400
            except Exception as e:
                row["error"] = str(e)
            report["results"].append(row)
        report["status"] = "completed"

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = EXPORT_DIR / f"meta_instagram_boost_{started_at.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Meta/Instagram boost status: {report['status']}")
    print(f"Queries: {len(queries)}")
    print(f"Report: {out}")


if __name__ == "__main__":
    main()

