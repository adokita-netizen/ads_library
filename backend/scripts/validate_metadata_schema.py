"""A27 (CI-007): ad_metadata schema validation.

Checks all ads for required metadata keys, warns on missing fields,
and generates a daily quality report.

Usage:
    python -m scripts.validate_metadata_schema
    python -m scripts.validate_metadata_schema --fix  # fill missing with defaults
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

# -- Add parent to path for module imports --
sys.path.insert(0, ".")

from app.core.database import SyncSessionLocal
from app.models.ad import (
    Ad,
    CREATIVE_FETCH_ID_KEYS,
    CREATIVE_FETCH_REASON_CODES,
    CREATIVE_ORIENTATIONS,
    normalize_creative_fetch_reason,
)


# Required metadata keys with expected types and default values
REQUIRED_SCHEMA = {
    # Core classification
    "fine_genre_en": {"type": str, "default": "other"},
    # Creative analysis
    "creative_analysis": {"type": dict, "default": None},
    # Metrics
    "ranking_metrics": {"type": dict, "default": None},
    "estimated_metrics": {"type": dict, "default": None},
    # Scoring
    "latest_hit_score": {"type": (int, float), "default": None},
    # R2 required keys
    "is_still_running": {"type": bool, "default": False},
    "days_running": {"type": (int, float), "default": 1},
    "creative_quality": {"type": dict, "default": None},
    "longevity_class": {"type": str, "default": "flash"},
    # A-0303 creative fetch governance (global gate)
    "source": {"type": str, "default": None},
}

# Recommended (non-critical) keys
RECOMMENDED_SCHEMA = {
    "scenario_structure": {"type": dict},
    "score_calibration": {"type": dict},
    "product_name": {"type": str},
    "keywords": {"type": list},
    "topic_label": {"type": str},
    "topic_tags": {"type": list},
    "topic_confidence": {"type": (int, float)},
    "matched_terms": {"type": list},
    "topic_evidence": {"type": list},
    "topic_candidates": {"type": list},
    "needs_topic_review": {"type": bool},
    "hit_drivers": {"type": list},
    "topic_dictionary_suggestions": {"type": list},
    "hit_prediction": {"type": dict},
    "prediction_features": {"type": dict},
    "text_quality": {"type": dict},
    "publisher_platforms": {"type": list},
    "estimation_method": {"type": str},
    "delivery_start_time": {"type": str},
    "freshness_score": {"type": (int, float)},
    "last_crawled_at": {"type": str},
    "crawl_source": {"type": str},
    "freshness_ttl_sec": {"type": int},
    "lp_snapshot_at": {"type": str},
    "lp_info": {"type": dict},
    "lp_fetch_error_code": {"type": str},
}

# Defaults for conditional keys introduced in A-0303.
CONDITIONAL_DEFAULTS = {
    "creative_fetch_status": "legacy_unknown",
    "creative_fetch_source": "legacy_unknown",
    "creative_fetched_at": "__NOW__",
    "orientation": "unknown",
    "aspect_ratio": "unknown",
    "creative_fetch_reason": "unknown",
}
_SUCCESSFUL_LP_PREFIXES = ("2", "3")
_LP_TINY_BODY_HARD_THRESHOLD = 80
_LP_TINY_BODY_SOFT_THRESHOLD = 120


def _lp_status_is_success(meta: dict) -> bool:
    lp_status = str(meta.get("lp_status") or meta.get("lp_fetch_status") or "").strip().lower()
    return any(lp_status.startswith(prefix) for prefix in _SUCCESSFUL_LP_PREFIXES)


def _should_flag_tiny_body(meta: dict) -> bool:
    lp_text_len = meta.get("lp_text_length")
    if not isinstance(lp_text_len, int) or lp_text_len <= 0:
        return False
    if not _lp_status_is_success(meta):
        return False
    if lp_text_len < _LP_TINY_BODY_HARD_THRESHOLD:
        return True

    has_title = bool(str(meta.get("title") or "").strip())
    has_h1 = int(meta.get("h1_count") or 0) > 0
    return lp_text_len < _LP_TINY_BODY_SOFT_THRESHOLD and not (has_title or has_h1)


def validate_ad(ad: Ad) -> dict:
    """Validate a single ad's metadata against the schema.

    Returns dict with 'missing_required', 'missing_recommended', 'type_errors'.
    """
    meta = ad.ad_metadata or {}
    result = {
        "ad_id": ad.id,
        "missing_required": [],
        "missing_recommended": [],
        "type_errors": [],
        "gate_violations": [],
    }

    for key, spec in REQUIRED_SCHEMA.items():
        if key not in meta or meta[key] is None:
            result["missing_required"].append(key)
        elif not isinstance(meta[key], spec["type"]):
            result["type_errors"].append(
                f"{key}: expected {spec['type'].__name__}, got {type(meta[key]).__name__}"
            )

    for key, spec in RECOMMENDED_SCHEMA.items():
        if key not in meta or meta[key] is None:
            result["missing_recommended"].append(key)

    # A-0303-1/2: conditional rules + quality gates
    has_any_creative = bool(ad.thumbnail_url or ad.image_url or ad.video_url or ad.snapshot_url)
    fetch_status = meta.get("creative_fetch_status")

    # If we have creative media, status/source/fetched_at must be present
    if has_any_creative:
        for k in ("creative_fetch_status", "creative_fetch_source", "creative_fetched_at"):
            if not meta.get(k):
                if k not in result["missing_required"]:
                    result["missing_required"].append(k)

    # source is mandatory for all records (A-0303-2 gate)
    if not meta.get("source"):
        if "source" not in result["missing_required"]:
            result["missing_required"].append("source")
        result["gate_violations"].append("source_missing")

    # failure reason is required when fetch status indicates failure
    if fetch_status in {"failed", "rejected", "blocked", "not_found"} and not meta.get("creative_fetch_reason"):
        result["missing_required"].append("creative_fetch_reason")

    # reason code dictionary (A-0303-P2)
    reason = meta.get("creative_fetch_reason")
    if reason is not None and normalize_creative_fetch_reason(reason) == "unknown_schema" and str(reason).strip() not in CREATIVE_FETCH_REASON_CODES:
        result["gate_violations"].append(f"reason_normalized_to_unknown_schema:{reason}")

    # video creatives should carry orientation/aspect_ratio
    if str(ad.creative_type or "").lower() == "video":
        if not meta.get("orientation"):
            result["missing_required"].append("orientation")
        if meta.get("aspect_ratio") is None:
            result["missing_required"].append("aspect_ratio")
    if meta.get("orientation") is not None:
        ori = str(meta.get("orientation")).strip().lower()
        if ori not in CREATIVE_ORIENTATIONS:
            result["gate_violations"].append(f"invalid_orientation:{ori}")

    # ad_id consistency gate (A-0303-2): reject mismatched linkage metadata
    for id_key in CREATIVE_FETCH_ID_KEYS:
        if id_key in meta and meta[id_key] is not None and str(meta[id_key]) != str(ad.id):
            result["gate_violations"].append(f"ad_id_mismatch:{id_key}={meta[id_key]}")
            break

    # A-BRW-1: crawl query metadata quality gates
    crawl_query = meta.get("crawl_query")
    if crawl_query is not None:
        normalized_crawl_query = str(crawl_query).replace("\u3000", " ").strip()
        if not normalized_crawl_query:
            result["gate_violations"].append("empty_crawl_query")
        if "crawl_result_count" not in meta:
            result["gate_violations"].append("crawl_result_count_missing")
        else:
            count_val = meta.get("crawl_result_count")
            if not isinstance(count_val, int):
                result["gate_violations"].append("crawl_result_count_invalid_type")
            elif count_val < 0:
                result["gate_violations"].append("crawl_result_count_negative")

    # A-LP-0303-2: LP quality gates (recorded in lp_quality_issue)
    lp_issues = meta.get("lp_quality_issue") or []
    if not isinstance(lp_issues, list):
        lp_issues = [str(lp_issues)]
    lp_issue_set = {str(x) for x in lp_issues if str(x).strip()}

    lp_status = str(meta.get("lp_status") or meta.get("lp_fetch_status") or "").strip().lower()
    lp_reason = str(meta.get("lp_fetch_reason") or "").strip().lower()
    lp_html_len = meta.get("lp_html_length")
    lp_text_len = meta.get("lp_text_length")

    if lp_status == "too_many_redirects" or lp_reason == "redirect_loop":
        result["gate_violations"].append("lp_redirect_loop")
        if "redirect_loop" not in lp_issue_set:
            result["gate_violations"].append("lp_quality_issue_missing:redirect_loop")

    if isinstance(lp_html_len, int) and lp_html_len == 0:
        result["gate_violations"].append("lp_empty_html")
        if "empty_html" not in lp_issue_set:
            result["gate_violations"].append("lp_quality_issue_missing:empty_html")

    if _should_flag_tiny_body(meta):
        result["gate_violations"].append("lp_tiny_body")
        if "tiny_body" not in lp_issue_set:
            result["gate_violations"].append("lp_quality_issue_missing:tiny_body")

    result["missing_required"] = sorted(set(result["missing_required"]))
    result["missing_recommended"] = sorted(set(result["missing_recommended"]))
    result["gate_violations"] = sorted(set(result["gate_violations"]))
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate ad_metadata schema")
    parser.add_argument("--fix", action="store_true", help="Fill missing required keys with defaults")
    parser.add_argument("--json-report", type=str, help="Export report to JSON file")
    parser.add_argument("--audit-log", type=str, default="exports/creative_fetch_gate_audit.jsonl", help="JSONL output for gate violations")
    parser.add_argument("--fail-on-gate", action="store_true", help="Exit 1 when source missing or ad_id mismatch is detected")
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Validating {total} ads...")

        # Aggregate results
        missing_required_counts = defaultdict(int)
        missing_recommended_counts = defaultdict(int)
        type_error_counts = defaultdict(int)
        gate_violation_counts = defaultdict(int)
        gate_audit_rows = []
        ads_with_issues = 0
        ads_fully_valid = 0
        fixed_count = 0
        per_ad_issues = []

        for ad in ads:
            result = validate_ad(ad)
            has_issue = bool(result["missing_required"] or result["type_errors"])

            if has_issue:
                ads_with_issues += 1
                per_ad_issues.append(result)
            else:
                ads_fully_valid += 1

            for key in result["missing_required"]:
                missing_required_counts[key] += 1
            for key in result["missing_recommended"]:
                missing_recommended_counts[key] += 1
            for err in result["type_errors"]:
                type_error_counts[err] += 1
            for gate in result["gate_violations"]:
                gate_violation_counts[gate] += 1
                gate_audit_rows.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ad_id": ad.id,
                    "gate": gate,
                    "creative_type": ad.creative_type.value if hasattr(ad.creative_type, "value") else str(ad.creative_type),
                    "source": (ad.ad_metadata or {}).get("source"),
                })

            # Fix mode: fill missing required keys with defaults
            if args.fix and (result["missing_required"] or result["gate_violations"]):
                meta = dict(ad.ad_metadata or {})
                for key in result["missing_required"]:
                    if key in REQUIRED_SCHEMA:
                        default = REQUIRED_SCHEMA[key]["default"]
                    else:
                        default = CONDITIONAL_DEFAULTS.get(key)
                    if default is not None:
                        if key == "creative_fetch_source" and meta.get("source"):
                            default = str(meta.get("source"))
                        if default == "__NOW__":
                            default = datetime.now(timezone.utc).isoformat()
                        meta[key] = default
                        fixed_count += 1

                # A-BRW-1: best-effort legacy normalization for crawl query gates.
                if "crawl_query" in meta:
                    normalized_crawl_query = str(meta.get("crawl_query") or "").replace("\u3000", " ").strip()
                    if normalized_crawl_query:
                        meta["crawl_query"] = normalized_crawl_query
                        if "crawl_result_count" not in meta:
                            meta["crawl_result_count"] = 0
                            fixed_count += 1
                    else:
                        # Empty crawl query is invalid for new writes; drop key for legacy rows.
                        meta.pop("crawl_query", None)
                        fixed_count += 1

                # A-LP-0303-2: ensure lp_quality_issue includes detected issues.
                lp_issues = meta.get("lp_quality_issue") or []
                if not isinstance(lp_issues, list):
                    lp_issues = [str(lp_issues)]
                lp_issue_set = {str(x) for x in lp_issues if str(x).strip()}
                if "lp_redirect_loop" in result["gate_violations"]:
                    lp_issue_set.add("redirect_loop")
                if "lp_empty_html" in result["gate_violations"]:
                    lp_issue_set.add("empty_html")
                if "lp_tiny_body" in result["gate_violations"]:
                    lp_issue_set.add("tiny_body")
                if set(lp_issues) != lp_issue_set:
                    meta["lp_quality_issue"] = sorted(lp_issue_set)
                    fixed_count += 1

                meta["schema_validated_at"] = datetime.now(timezone.utc).isoformat()
                if "creative_fetch_reason" in meta:
                    meta["creative_fetch_reason"] = normalize_creative_fetch_reason(meta.get("creative_fetch_reason"))
                if "orientation" in meta and meta.get("orientation") is not None:
                    meta["orientation"] = str(meta["orientation"]).strip().lower()
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

        if args.fix and fixed_count > 0:
            session.commit()

        # Print report
        print(f"\n{'='*60}")
        print(f"  ad_metadata Schema Validation Report")
        print(f"  Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*60}")
        print(f"\n  Total ads: {total}")
        print(f"  Fully valid: {ads_fully_valid} ({ads_fully_valid*100/total:.1f}%)")
        print(f"  With issues: {ads_with_issues} ({ads_with_issues*100/total:.1f}%)")

        if missing_required_counts:
            print(f"\n  REQUIRED keys missing:")
            for key, count in sorted(missing_required_counts.items(), key=lambda x: -x[1]):
                pct = count * 100 / total
                bar = "#" * int(pct / 2)
                print(f"    {key:30s} {count:4d}/{total} ({pct:5.1f}%) {bar}")
        else:
            print(f"\n  All required keys present!")

        if missing_recommended_counts:
            print(f"\n  RECOMMENDED keys missing:")
            for key, count in sorted(missing_recommended_counts.items(), key=lambda x: -x[1]):
                pct = count * 100 / total
                print(f"    {key:30s} {count:4d}/{total} ({pct:5.1f}%)")

        if type_error_counts:
            print(f"\n  TYPE errors:")
            for err, count in sorted(type_error_counts.items(), key=lambda x: -x[1]):
                print(f"    {err}: {count} ads")

        if gate_violation_counts:
            print(f"\n  QUALITY gate violations:")
            for gate, count in sorted(gate_violation_counts.items(), key=lambda x: -x[1]):
                pct = count * 100 / total if total else 0
                print(f"    {gate:30s} {count:4d}/{total} ({pct:5.1f}%)")

        if args.fix:
            print(f"\n  Fixed: {fixed_count} missing defaults filled")

        # Quality grade
        required_fill = (total - ads_with_issues) / total if total else 0
        if required_fill >= 0.95:
            grade = "A"
        elif required_fill >= 0.85:
            grade = "B"
        elif required_fill >= 0.70:
            grade = "C"
        elif required_fill >= 0.50:
            grade = "D"
        else:
            grade = "F"
        print(f"\n  Schema compliance grade: {grade} ({required_fill*100:.1f}% valid)")

        # JSON report
        if args.json_report:
            report = {
                "date": datetime.now(timezone.utc).isoformat(),
                "total_ads": total,
                "fully_valid": ads_fully_valid,
                "with_issues": ads_with_issues,
                "grade": grade,
                "compliance_pct": round(required_fill * 100, 1),
                "missing_required": dict(missing_required_counts),
                "missing_recommended": dict(missing_recommended_counts),
                "type_errors": dict(type_error_counts),
                "gate_violations": dict(gate_violation_counts),
                "sample_issues": per_ad_issues[:20],
            }
            with open(args.json_report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n  Report exported: {args.json_report}")

        # Gate audit log (A-0303-2)
        if gate_audit_rows:
            os.makedirs(os.path.dirname(args.audit_log) or ".", exist_ok=True)
            with open(args.audit_log, "a", encoding="utf-8") as f:
                for row in gate_audit_rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  Gate audit rows: {len(gate_audit_rows)} -> {args.audit_log}")

        print()

        if args.fail_on_gate and gate_audit_rows:
            raise SystemExit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
