import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "api_compatibility_review.py"
    spec = importlib.util.spec_from_file_location("api_compatibility_review", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_api_compatibility_review_assets_are_complete():
    module = _load_module()
    report = module.build_review_report()

    assert report["review_ready"] is True
    assert report["missing_sections"] == []
    assert report["missing_contract_tests"] == []
    assert "Which endpoints changed?" in report["required_review_questions"]


def test_api_compatibility_guideline_mentions_breaking_changes():
    repo_root = Path(__file__).resolve().parents[2]
    guideline = (repo_root / "docs" / "API_COMPATIBILITY_GUIDELINES.md").read_text(encoding="utf-8")

    assert "Breaking changes require" in guideline
    assert "Do not remove existing response fields" in guideline
