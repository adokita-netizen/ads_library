#!/usr/bin/env python3
"""Generate daily monitoring snapshot for model quality and drift.

Optionally publishes summary metrics to CloudWatch so dashboards and alarms
can track deployed model health without reading local JSON artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
EXPORTS_DIR = BASE_DIR / "exports"
REGISTRY_PATH = EXPORTS_DIR / "model_registry.json"
FEATURE_MATRIX_PATH = EXPORTS_DIR / "feature_matrix.csv"
SNAPSHOT_PATH = EXPORTS_DIR / "mlops_monitoring_snapshot.json"
CREATIVE_AUDIT_REPORTS_PATH = BASE_DIR / "data" / "creative_library_audit_reports.json"
_CW_NAMESPACE = "VAAP/MLOps"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_feature_stats(path: Path) -> dict:
    if not path.exists():
        return {"rows": 0, "means": {}}

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"rows": 0, "means": {}}

    numeric_cols = [c for c in rows[0].keys() if c not in {"ad_id"}]
    sums = {c: 0.0 for c in numeric_cols}
    counts = {c: 0 for c in numeric_cols}
    for row in rows:
        for c in numeric_cols:
            try:
                v = float(row.get(c, 0) or 0)
            except Exception:
                v = 0.0
            sums[c] += v
            counts[c] += 1

    means = {c: (sums[c] / counts[c] if counts[c] else 0.0) for c in numeric_cols}
    return {"rows": len(rows), "means": means}


def _top_drift(current: dict, baseline: dict, top_n: int = 10) -> list[dict]:
    drifts = []
    keys = set(current.keys()) | set(baseline.keys())
    for k in keys:
        cur = float(current.get(k, 0.0) or 0.0)
        base = float(baseline.get(k, 0.0) or 0.0)
        delta = cur - base
        drifts.append(
            {
                "feature": k,
                "current_mean": round(cur, 6),
                "baseline_mean": round(base, 6),
                "delta": round(delta, 6),
                "abs_delta": round(abs(delta), 6),
            }
        )
    drifts.sort(key=lambda x: x["abs_delta"], reverse=True)
    return drifts[:top_n]


def _build_snapshot() -> dict:
    registry = _load_json(REGISTRY_PATH, {"versions": []})
    versions = registry.get("versions", [])
    deployed = [v for v in versions if v.get("deployed")]
    deployed.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    latest = deployed[0] if deployed else None

    current_stats = _read_feature_stats(FEATURE_MATRIX_PATH)
    baseline_means = {}
    if latest:
        baseline_means = (latest.get("feature_profile") or {}).get("means", {})

    top_drift = _top_drift(current_stats.get("means", {}), baseline_means, top_n=10)
    max_abs_drift = max((d["abs_delta"] for d in top_drift), default=0.0)
    drift_status = "ok" if max_abs_drift < 0.15 else "warning"
    creative_reports = _load_json(CREATIVE_AUDIT_REPORTS_PATH, [])
    latest_quality = creative_reports[-1] if isinstance(creative_reports, list) and creative_reports else {}
    bedrock_summary = ((latest_quality or {}).get("bedrock_precision_roi_audit") or {}).get("summary", {})

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "latest_version": latest.get("version") if latest else None,
        "latest_metrics": (latest or {}).get("metrics", {}),
        "feature_rows": current_stats.get("rows", 0),
        "drift_status": drift_status,
        "max_abs_drift": round(float(max_abs_drift), 6),
        "top_feature_drift": top_drift,
        "bedrock_precision_roi": {
            "rule_only_count": int(bedrock_summary.get("rule_only_count", 0) or 0),
            "bedrock_used_count": int(bedrock_summary.get("bedrock_used_count", 0) or 0),
            "manual_review_count": int(bedrock_summary.get("manual_review_count", 0) or 0),
            "review_required_count": int(bedrock_summary.get("review_required_count", 0) or 0),
            "bedrock_valuable_count": int(bedrock_summary.get("bedrock_valuable_count", 0) or 0),
        },
    }


def _publish_cloudwatch_metrics(snapshot: dict) -> dict:
    import boto3

    env = os.getenv("APP_ENV", "dev").strip() or "dev"
    metrics = [
        {
            "MetricName": "DriftMaxAbs",
            "Dimensions": [{"Name": "Environment", "Value": env}],
            "Timestamp": datetime.now(timezone.utc),
            "Value": float(snapshot.get("max_abs_drift", 0.0) or 0.0),
            "Unit": "None",
        },
        {
            "MetricName": "FeatureRows",
            "Dimensions": [{"Name": "Environment", "Value": env}],
            "Timestamp": datetime.now(timezone.utc),
            "Value": float(snapshot.get("feature_rows", 0) or 0),
            "Unit": "Count",
        },
        {
            "MetricName": "DriftWarning",
            "Dimensions": [{"Name": "Environment", "Value": env}],
            "Timestamp": datetime.now(timezone.utc),
            "Value": 1.0 if snapshot.get("drift_status") == "warning" else 0.0,
            "Unit": "Count",
        },
    ]

    latest_metrics = snapshot.get("latest_metrics") or {}
    try:
        test_accuracy = float(latest_metrics.get("test_accuracy", 0.0) or 0.0)
    except Exception:
        test_accuracy = 0.0
    metrics.append(
        {
            "MetricName": "ModelTestAccuracy",
            "Dimensions": [{"Name": "Environment", "Value": env}],
            "Timestamp": datetime.now(timezone.utc),
            "Value": test_accuracy,
            "Unit": "None",
        }
    )

    cloudwatch = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
    cloudwatch.put_metric_data(Namespace=_CW_NAMESPACE, MetricData=metrics)
    return {
        "published": True,
        "namespace": _CW_NAMESPACE,
        "metric_names": [metric["MetricName"] for metric in metrics],
        "environment": env,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MLOps monitoring snapshot")
    parser.add_argument(
        "--publish-cloudwatch",
        action="store_true",
        default=os.getenv("MLOPS_PUBLISH_CLOUDWATCH", "").lower() in {"1", "true", "yes"},
        help="Publish summary metrics to CloudWatch",
    )
    args = parser.parse_args()

    snapshot = _build_snapshot()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.publish_cloudwatch:
        try:
            snapshot["cloudwatch"] = _publish_cloudwatch_metrics(snapshot)
        except Exception as exc:
            snapshot["cloudwatch"] = {"published": False, "error": str(exc)}
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
