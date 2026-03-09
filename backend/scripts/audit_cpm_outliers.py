"""DPRO-DATA-002: Audit CPM outliers used in spend estimation.

Produces a CPM outlier report using IQR bounds per platform.
No database writes are performed.

Usage:
    python -m scripts.audit_cpm_outliers
    python -m scripts.audit_cpm_outliers --min-samples 50 --top 30
    python -m scripts.audit_cpm_outliers --json-report exports/cpm_outliers.json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


DEFAULT_TOP = 20
DEFAULT_MIN_SAMPLES = 30
HARD_MIN_CPM = 50
HARD_MAX_CPM = 20000


def _extract_cpm(ad: Ad) -> float | None:
    meta = ad.ad_metadata or {}
    if isinstance(meta, dict):
        v = meta.get("estimated_cpm_jpy")
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    if isinstance(ad.cpm, (int, float)) and ad.cpm > 0:
        return float(ad.cpm)
    return None


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def _iqr_bounds(values: list[float]) -> tuple[float, float, float, float]:
    s = sorted(values)
    q1 = _percentile(s, 0.25)
    q3 = _percentile(s, 0.75)
    iqr = max(0.0, q3 - q1)
    lower = max(HARD_MIN_CPM, q1 - 1.5 * iqr)
    upper = min(HARD_MAX_CPM, q3 + 1.5 * iqr)
    return q1, q3, lower, upper


def audit_cpm_outliers(session, min_samples: int = DEFAULT_MIN_SAMPLES, top: int = DEFAULT_TOP) -> dict:
    rows = session.query(Ad.id, Ad.platform, Ad.cpm, Ad.ad_metadata).all()
    platform_cpms: dict[str, list[float]] = {}
    ad_records: list[dict] = []

    for ad_id, platform, cpm, meta in rows:
        ad = type("A", (), {"id": ad_id, "platform": platform, "cpm": cpm, "ad_metadata": meta})()
        value = _extract_cpm(ad)
        if value is None:
            continue
        p = str(platform)
        platform_cpms.setdefault(p, []).append(value)
        ad_records.append({"ad_id": ad_id, "platform": p, "cpm_jpy": value})

    platform_bounds = {}
    for p, vals in platform_cpms.items():
        if len(vals) < min_samples:
            continue
        q1, q3, low, high = _iqr_bounds(vals)
        platform_bounds[p] = {
            "count": len(vals),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "lower_bound": round(low, 2),
            "upper_bound": round(high, 2),
        }

    outliers = []
    for rec in ad_records:
        b = platform_bounds.get(rec["platform"])
        if not b:
            continue
        cpm_val = rec["cpm_jpy"]
        if cpm_val < b["lower_bound"] or cpm_val > b["upper_bound"]:
            rec["bounds"] = {"lower": b["lower_bound"], "upper": b["upper_bound"]}
            rec["distance_ratio"] = round(
                cpm_val / b["upper_bound"], 3
            ) if cpm_val > b["upper_bound"] and b["upper_bound"] > 0 else round(
                b["lower_bound"] / cpm_val, 3
            ) if cpm_val < b["lower_bound"] and cpm_val > 0 else 0
            outliers.append(rec)

    outliers.sort(key=lambda x: abs(x["cpm_jpy"] - x["bounds"]["upper"]), reverse=True)
    outliers = outliers[:top]

    return {
        "scanned_ads": len(rows),
        "ads_with_cpm": len(ad_records),
        "platform_bounds": platform_bounds,
        "outlier_count": len(outliers),
        "outliers": outliers,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit CPM outliers by platform (IQR method)")
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
                        help=f"Minimum CPM samples per platform (default: {DEFAULT_MIN_SAMPLES})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help=f"Max outliers to print (default: {DEFAULT_TOP})")
    parser.add_argument("--json-report", type=str, help="Export full report to JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  DPRO-DATA-002: CPM Outlier Audit")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        report = audit_cpm_outliers(session, min_samples=args.min_samples, top=args.top)

        print(f"\n  Ads scanned:           {report['scanned_ads']}")
        print(f"  Ads with CPM:          {report['ads_with_cpm']}")
        print(f"  Platforms analyzed:    {len(report['platform_bounds'])}")
        print(f"  Outliers (reported):   {report['outlier_count']}")

        if report["platform_bounds"]:
            print("\n  Platform bounds (IQR):")
            for platform, b in sorted(report["platform_bounds"].items()):
                print(
                    f"    - {platform}: n={b['count']} q1={b['q1']} q3={b['q3']} "
                    f"range=[{b['lower_bound']}, {b['upper_bound']}]"
                )

        if report["outliers"]:
            print("\n  Top outliers:")
            for item in report["outliers"][:args.top]:
                print(
                    f"    - ad_id={item['ad_id']} platform={item['platform']} cpm={round(item['cpm_jpy'],2)} "
                    f"(bounds {item['bounds']['lower']}..{item['bounds']['upper']})"
                )

        if args.json_report:
            os.makedirs(os.path.dirname(args.json_report) or ".", exist_ok=True)
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "report": report,
            }
            with open(args.json_report, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"\n  Exported: {args.json_report}")

        print()
    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

