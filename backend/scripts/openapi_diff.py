"""Generate and diff the committed OpenAPI specification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "backend" / "openapi.json"
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _relative_posix(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _sorted_methods(path_item: dict[str, Any]) -> list[str]:
    return sorted(k for k, v in path_item.items() if isinstance(v, dict))


def load_committed_spec() -> dict[str, Any]:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


def generate_current_spec() -> dict[str, Any]:
    from app.main import app

    return app.openapi()


def compare_specs(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_paths = baseline.get("paths", {})
    current_paths = current.get("paths", {})

    added_paths = sorted(set(current_paths) - set(baseline_paths))
    removed_paths = sorted(set(baseline_paths) - set(current_paths))
    changed_paths: list[dict[str, Any]] = []

    shared_paths = sorted(set(baseline_paths) & set(current_paths))
    for path in shared_paths:
        before_item = baseline_paths.get(path, {})
        after_item = current_paths.get(path, {})
        before_methods = _sorted_methods(before_item)
        after_methods = _sorted_methods(after_item)
        if before_item != after_item:
            changed_paths.append(
                {
                    "path": path,
                    "added_methods": sorted(set(after_methods) - set(before_methods)),
                    "removed_methods": sorted(set(before_methods) - set(after_methods)),
                    "changed_methods": sorted(set(before_methods) & set(after_methods)),
                }
            )

    baseline_schemas = set((baseline.get("components") or {}).get("schemas", {}))
    current_schemas = set((current.get("components") or {}).get("schemas", {}))

    return {
        "changed": bool(added_paths or removed_paths or changed_paths or baseline != current),
        "baseline": {
            "path_count": len(baseline_paths),
            "schema_count": len(baseline_schemas),
        },
        "current": {
            "path_count": len(current_paths),
            "schema_count": len(current_schemas),
        },
        "summary": {
            "added_path_count": len(added_paths),
            "removed_path_count": len(removed_paths),
            "changed_path_count": len(changed_paths),
            "added_schema_count": len(current_schemas - baseline_schemas),
            "removed_schema_count": len(baseline_schemas - current_schemas),
        },
        "added_paths": added_paths,
        "removed_paths": removed_paths,
        "changed_paths": changed_paths,
        "added_schemas": sorted(current_schemas - baseline_schemas),
        "removed_schemas": sorted(baseline_schemas - current_schemas),
    }


def build_report() -> dict[str, Any]:
    baseline = load_committed_spec()
    current = generate_current_spec()
    diff = compare_specs(baseline, current)
    return {
        "openapi_path": _relative_posix(OPENAPI_PATH),
        "openapi_version": current.get("openapi"),
        "info_version": (current.get("info") or {}).get("version"),
        **diff,
    }


def write_current_spec(spec: dict[str, Any]) -> None:
    OPENAPI_PATH.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _print_text(report: dict[str, Any]) -> None:
    print(f"changed={report['changed']}")
    print(f"openapi_path={report['openapi_path']}")
    print(
        "summary="
        f"added_paths:{report['summary']['added_path_count']},"
        f"removed_paths:{report['summary']['removed_path_count']},"
        f"changed_paths:{report['summary']['changed_path_count']},"
        f"added_schemas:{report['summary']['added_schema_count']},"
        f"removed_schemas:{report['summary']['removed_schema_count']}"
    )
    if report["added_paths"]:
        print("added_paths=" + ",".join(report["added_paths"]))
    if report["removed_paths"]:
        print("removed_paths=" + ",".join(report["removed_paths"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and diff OpenAPI spec.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if the committed OpenAPI spec is stale.")
    parser.add_argument("--write", action="store_true", help="Overwrite backend/openapi.json with the current generated spec.")
    args = parser.parse_args()

    current = generate_current_spec()
    if args.write:
        write_current_spec(current)

    report = {
        "openapi_path": _relative_posix(OPENAPI_PATH),
        "openapi_version": current.get("openapi"),
        "info_version": (current.get("info") or {}).get("version"),
        **compare_specs(load_committed_spec(), current),
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text(report)

    if args.check and report["changed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
