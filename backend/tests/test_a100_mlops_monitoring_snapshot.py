import csv
import json
import types
from pathlib import Path

from scripts import mlops_monitoring_snapshot as snapshot_mod


def test_a100_build_snapshot_uses_latest_deployed_and_computes_drift(tmp_path, monkeypatch):
    exports = tmp_path / "exports"
    exports.mkdir()
    registry = {
        "versions": [
            {
                "version": "v-old",
                "created_at": "2026-03-01T00:00:00+00:00",
                "deployed": True,
                "metrics": {"test_accuracy": 0.71},
                "feature_profile": {"means": {"ctr": 0.10, "cvr": 0.05}},
            }
        ]
    }
    creative_reports = [
        {
            "date": "2026-03-08",
            "bedrock_precision_roi_audit": {
                "summary": {
                    "rule_only_count": 4,
                    "bedrock_used_count": 7,
                    "manual_review_count": 2,
                    "review_required_count": 2,
                    "bedrock_valuable_count": 3,
                }
            },
        }
    ]
    (exports / "model_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (tmp_path / "creative_library_audit_reports.json").write_text(json.dumps(creative_reports), encoding="utf-8")
    with (exports / "feature_matrix.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ad_id", "ctr", "cvr"])
        writer.writeheader()
        writer.writerow({"ad_id": "1", "ctr": "0.32", "cvr": "0.05"})
        writer.writerow({"ad_id": "2", "ctr": "0.28", "cvr": "0.05"})

    monkeypatch.setattr(snapshot_mod, "REGISTRY_PATH", exports / "model_registry.json")
    monkeypatch.setattr(snapshot_mod, "FEATURE_MATRIX_PATH", exports / "feature_matrix.csv")
    monkeypatch.setattr(snapshot_mod, "CREATIVE_AUDIT_REPORTS_PATH", tmp_path / "creative_library_audit_reports.json")

    snapshot = snapshot_mod._build_snapshot()

    assert snapshot["latest_version"] == "v-old"
    assert snapshot["feature_rows"] == 2
    assert snapshot["max_abs_drift"] >= 0.19
    assert snapshot["drift_status"] == "warning"
    assert snapshot["latest_metrics"]["test_accuracy"] == 0.71
    assert snapshot["bedrock_precision_roi"]["bedrock_used_count"] == 7


def test_a100_publish_cloudwatch_metrics_sends_expected_metric_names(monkeypatch):
    calls = {}

    class _FakeCW:
        def put_metric_data(self, Namespace, MetricData):  # noqa: N803
            calls["Namespace"] = Namespace
            calls["MetricData"] = MetricData

    fake_boto3 = types.SimpleNamespace(client=lambda service_name, region_name=None: _FakeCW())
    monkeypatch.setitem(__import__("sys").modules, "boto3", fake_boto3)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")

    res = snapshot_mod._publish_cloudwatch_metrics(
        {
            "max_abs_drift": 0.17,
            "feature_rows": 123,
            "drift_status": "warning",
            "latest_metrics": {"test_accuracy": 0.64},
        }
    )

    assert res["published"] is True
    assert calls["Namespace"] == "VAAP/MLOps"
    metric_names = [metric["MetricName"] for metric in calls["MetricData"]]
    assert metric_names == ["DriftMaxAbs", "FeatureRows", "DriftWarning", "ModelTestAccuracy"]
