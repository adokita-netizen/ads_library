import json
import sys
from pathlib import Path

from scripts import mlops_retrain_pipeline as pipeline_mod


def test_a100_retrain_pipeline_publishes_version_and_latest_alias(tmp_path, monkeypatch):
    exports = tmp_path / "exports"
    models = tmp_path / "models"
    versions = models / "versions"
    exports.mkdir()
    versions.mkdir(parents=True)

    (models / "hit_predictor.pkl").write_bytes(b"model-bytes")
    (exports / "feature_importance.json").write_text(
        json.dumps(
            {
                "model_info": {
                    "model_type": "rf",
                    "test_accuracy": 0.81,
                    "precision": 0.8,
                    "recall": 0.79,
                    "f1": 0.795,
                    "cv_mean": 0.77,
                    "total_samples": 42,
                    "feature_count": 3,
                }
            }
        ),
        encoding="utf-8",
    )
    (exports / "feature_matrix.csv").write_text(
        "ad_id,ctr,cvr\n1,0.1,0.2\n2,0.2,0.3\n",
        encoding="utf-8-sig",
    )
    (exports / "model_registry.json").write_text(json.dumps({"versions": []}), encoding="utf-8")

    monkeypatch.setattr(pipeline_mod, "EXPORTS_DIR", exports)
    monkeypatch.setattr(pipeline_mod, "MODELS_DIR", models)
    monkeypatch.setattr(pipeline_mod, "MODEL_PATH", models / "hit_predictor.pkl")
    monkeypatch.setattr(pipeline_mod, "MODEL_VERSIONS_DIR", versions)
    monkeypatch.setattr(pipeline_mod, "MODEL_LATEST_PATH", models / "hit_predictor_latest.pkl")
    monkeypatch.setattr(pipeline_mod, "REGISTRY_PATH", exports / "model_registry.json")
    monkeypatch.setattr(pipeline_mod, "TRAIN_REPORT_PATH", exports / "feature_importance.json")
    monkeypatch.setattr(pipeline_mod, "FEATURE_MATRIX_PATH", exports / "feature_matrix.csv")
    monkeypatch.setattr(pipeline_mod, "_run_python_script", lambda script_name: None)

    uploads = []
    copies = []

    def _fake_upload(bucket, model_key, metadata_key, metadata):
        uploads.append(
            {
                "bucket": bucket,
                "model_key": model_key,
                "metadata_key": metadata_key,
                "metadata": metadata,
            }
        )

    def _fake_copy(bucket, source_key, destination_key):
        copies.append(
            {
                "bucket": bucket,
                "source_key": source_key,
                "destination_key": destination_key,
            }
        )

    monkeypatch.setattr(pipeline_mod, "_upload_to_s3", _fake_upload)
    monkeypatch.setattr(pipeline_mod, "_copy_s3_object", _fake_copy)
    monkeypatch.setattr(
        sys,
        "argv",
        ["mlops_retrain_pipeline.py", "--s3-bucket", "test-bucket", "--s3-prefix", "mlops/test"],
    )

    rc = pipeline_mod.main()

    assert rc == 0
    assert len(uploads) == 2
    assert uploads[0]["model_key"].startswith("mlops/test/versions/hit_predictor_v")
    assert uploads[0]["metadata_key"].startswith("mlops/test/metadata/v")
    assert uploads[1]["metadata_key"] == "mlops/test/latest.json"
    assert uploads[1]["metadata"]["latest_model_key"] == "mlops/test/hit_predictor_latest.pkl"
    assert copies == [
        {
            "bucket": "test-bucket",
            "source_key": uploads[0]["model_key"],
            "destination_key": "mlops/test/hit_predictor_latest.pkl",
        }
    ]


def test_a100_deploy_script_verifies_registered_worker_image():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "deploy_worker_image_a100.ps1"
    content = script_path.read_text(encoding="utf-8")

    assert 'docker info --format "{{.ServerVersion}}"' in content
    assert "Set-Content -Path $tmp -Encoding utf8NoBOM" in content
    assert "Verify registered task definition points at new worker image..." in content
    assert "taskDefinition.taskDefinitionArn" in content
    assert "Worker task definition image mismatch" in content
