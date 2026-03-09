"""Validate API compatibility review assets for this repository."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / ".agent-tasks" / "api_compatibility_review_manifest.json"


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def build_review_report() -> dict[str, Any]:
    manifest = load_manifest()
    guideline_path = REPO_ROOT / str(manifest["guideline_path"])
    guideline_text = guideline_path.read_text(encoding="utf-8") if guideline_path.exists() else ""

    missing_sections = [
        section for section in manifest["required_sections"]
        if f"## {section}" not in guideline_text
    ]
    missing_tests = [
        path for path in manifest["critical_contract_tests"]
        if not (REPO_ROOT / path).exists()
    ]
    review_ready = not missing_sections and not missing_tests and guideline_path.exists()

    return {
        "review_ready": review_ready,
        "guideline_path": manifest["guideline_path"],
        "manifest_version": manifest["version"],
        "required_sections": manifest["required_sections"],
        "missing_sections": missing_sections,
        "critical_contract_tests": manifest["critical_contract_tests"],
        "missing_contract_tests": missing_tests,
        "required_review_questions": manifest["required_review_questions"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check API compatibility review assets.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if review assets are incomplete.")
    args = parser.parse_args()

    report = build_review_report()

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"review_ready={report['review_ready']}")
        print(f"guideline_path={report['guideline_path']}")
        print(f"missing_sections={','.join(report['missing_sections']) or '-'}")
        print(f"missing_contract_tests={','.join(report['missing_contract_tests']) or '-'}")

    if args.check and not report["review_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
