#!/usr/bin/env python3
"""MLOps retrain pipeline for hit predictor.

Flow:
1. Build feature matrix from latest ads.
2. Train hit predictor model.
3. Apply quality gate against latest deployed model.
4. Version and promote model.
5. Persist registry metadata locally and optionally to S3.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
EXPORTS_DIR = BASE_DIR / "exports"
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "hit_predictor.pkl"
MODEL_VERSIONS_DIR = MODELS_DIR / "versions"
MODEL_LATEST_PATH = MODELS_DIR / "hit_predictor_latest.pkl"
REGISTRY_PATH = EXPORTS_DIR / "model_registry.json"
TRAIN_REPORT_PATH = EXPORTS_DIR / "feature_importance.json"
FEATURE_MATRIX_PATH = EXPORTS_DIR / "feature_matrix.csv"


def _run_python_script(script_name: str) -> None:
    script_path = BASE_DIR / "scripts" / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed: exit={result.returncode}\n"
            f"stdout={result.stdout[-2000:]}\n"
            f"stderr={result.stderr[-2000:]}"
        )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_deployed(registry: dict) -> dict | None:
    versions = registry.get("versions", [])
    deployed = [v for v in versions if v.get("deployed")]
    if not deployed:
        return None
    deployed.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return deployed[0]


def _extract_train_metrics() -> dict:
    report = _load_json(TRAIN_REPORT_PATH, {})
    model_info = report.get("model_info", {})
    return {
        "model_type": model_info.get("model_type", "unknown"),
        "test_accuracy": float(model_info.get("test_accuracy", 0.0) or 0.0),
        "precision": float(model_info.get("precision", 0.0) or 0.0),
        "recall": float(model_info.get("recall", 0.0) or 0.0),
        "f1": float(model_info.get("f1", 0.0) or 0.0),
        "cv_mean": float(model_info.get("cv_mean", 0.0) or 0.0),
        "samples": int(model_info.get("total_samples", 0) or 0),
        "feature_count": int(model_info.get("feature_count", 0) or 0),
    }


def _read_feature_profile() -> dict:
    if not FEATURE_MATRIX_PATH.exists():
        return {"rows": 0, "means": {}}
    import csv

    with FEATURE_MATRIX_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {"rows": 0, "means": {}}

    numeric_cols = [c for c in rows[0].keys() if c != "ad_id"]
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


def _quality_gate(
    new_metrics: dict,
    prev_metrics: dict | None,
    min_accuracy: float,
    max_accuracy_drop: float,
) -> tuple[bool, str]:
    new_acc = float(new_metrics.get("test_accuracy", 0.0) or 0.0)
    if new_acc < min_accuracy:
        return False, f"test_accuracy {new_acc:.4f} < minimum {min_accuracy:.4f}"
    if prev_metrics:
        prev_acc = float(prev_metrics.get("test_accuracy", 0.0) or 0.0)
        if prev_acc > 0 and (prev_acc - new_acc) > max_accuracy_drop:
            return (
                False,
                f"accuracy_drop {(prev_acc - new_acc):.4f} exceeded {max_accuracy_drop:.4f}",
            )
    return True, "quality gate passed"


def _upload_to_s3(bucket: str, model_key: str, metadata_key: str, metadata: dict) -> None:
    import boto3

    s3 = boto3.client("s3")
    s3.upload_file(str(MODEL_PATH), bucket, model_key)
    s3.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _copy_s3_object(bucket: str, source_key: str, destination_key: str) -> None:
    import boto3

    s3 = boto3.client("s3")
    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": source_key},
        Key=destination_key,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="MLOps retrain pipeline")
    parser.add_argument("--min-accuracy", type=float, default=0.60)
    parser.add_argument("--max-accuracy-drop", type=float, default=0.03)
    parser.add_argument("--s3-bucket", default=os.getenv("AWS_S3_BUCKET", ""))
    parser.add_argument("--s3-prefix", default=os.getenv("MLOPS_MODEL_PREFIX", "mlops/hit_predictor"))
    args = parser.parse_args()

    print("=== MLOps retrain pipeline ===")
    print(f"base_dir={BASE_DIR}")

    _run_python_script("build_prediction_features.py")
    _run_python_script("train_hit_predictor.py")

    if not MODEL_PATH.exists():
        raise RuntimeError(f"model file not found: {MODEL_PATH}")

    new_metrics = _extract_train_metrics()
    feature_profile = _read_feature_profile()
    registry = _load_json(REGISTRY_PATH, {"versions": []})
    prev = _latest_deployed(registry)
    prev_metrics = (prev or {}).get("metrics")
    gate_ok, gate_reason = _quality_gate(
        new_metrics=new_metrics,
        prev_metrics=prev_metrics,
        min_accuracy=args.min_accuracy,
        max_accuracy_drop=args.max_accuracy_drop,
    )

    now = datetime.now(timezone.utc)
    version = now.strftime("v%Y%m%d%H%M%S")
    created_at = now.isoformat()

    entry = {
        "version": version,
        "created_at": created_at,
        "metrics": new_metrics,
        "deployed": bool(gate_ok),
        "gate_reason": gate_reason,
        "artifact": {
            "path": f"models/versions/hit_predictor_{version}.pkl",
        },
        "feature_profile": feature_profile,
    }

    MODEL_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    versioned_path = MODEL_VERSIONS_DIR / f"hit_predictor_{version}.pkl"
    shutil.copyfile(MODEL_PATH, versioned_path)

    if gate_ok:
        shutil.copyfile(MODEL_PATH, MODEL_LATEST_PATH)
        registry["latest_version"] = version

    registry.setdefault("versions", []).append(entry)
    _save_json(REGISTRY_PATH, registry)

    s3_result = {"uploaded": False}
    if args.s3_bucket:
        try:
            model_key = f"{args.s3_prefix}/versions/hit_predictor_{version}.pkl"
            metadata_key = f"{args.s3_prefix}/metadata/{version}.json"
            _upload_to_s3(
                bucket=args.s3_bucket,
                model_key=model_key,
                metadata_key=metadata_key,
                metadata=entry,
            )
            if gate_ok:
                latest_model_key = f"{args.s3_prefix}/hit_predictor_latest.pkl"
                _copy_s3_object(
                    bucket=args.s3_bucket,
                    source_key=model_key,
                    destination_key=latest_model_key,
                )
                latest_key = f"{args.s3_prefix}/latest.json"
                _upload_to_s3(
                    bucket=args.s3_bucket,
                    model_key=f"{args.s3_prefix}/versions/hit_predictor_{version}.pkl",
                    metadata_key=latest_key,
                    metadata={
                        "latest_version": version,
                        "updated_at": created_at,
                        "latest_model_key": latest_model_key,
                    },
                )
                s3_result = {
                    "uploaded": True,
                    "bucket": args.s3_bucket,
                    "version_model_key": model_key,
                    "version_metadata_key": metadata_key,
                    "latest_model_key": latest_model_key,
                    "latest_metadata_key": latest_key,
                }
            else:
                s3_result = {
                    "uploaded": True,
                    "bucket": args.s3_bucket,
                    "version_model_key": model_key,
                    "version_metadata_key": metadata_key,
                }
        except Exception as exc:
            s3_result = {"uploaded": False, "error": str(exc)}

    result = {
        "status": "deployed" if gate_ok else "rejected",
        "version": version,
        "gate_reason": gate_reason,
        "metrics": new_metrics,
        "s3": s3_result,
    }
    out_path = EXPORTS_DIR / "mlops_retrain_result.json"
    _save_json(out_path, result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if gate_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
