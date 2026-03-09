import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "openapi_diff.py"
    spec = importlib.util.spec_from_file_location("openapi_diff", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_compare_specs_reports_path_and_schema_changes():
    module = _load_module()

    baseline = {
        "openapi": "3.1.0",
        "info": {"version": "1.0.0"},
        "paths": {
            "/api/v1/example": {"get": {"operationId": "before"}},
            "/api/v1/remove": {"get": {"operationId": "remove_me"}},
        },
        "components": {"schemas": {"BeforeModel": {"type": "object"}}},
    }
    current = {
        "openapi": "3.1.0",
        "info": {"version": "1.0.1"},
        "paths": {
            "/api/v1/example": {"get": {"operationId": "after"}, "post": {"operationId": "create"}},
            "/api/v1/add": {"get": {"operationId": "new_path"}},
        },
        "components": {"schemas": {"AfterModel": {"type": "object"}}},
    }

    report = module.compare_specs(baseline, current)

    assert report["changed"] is True
    assert report["added_paths"] == ["/api/v1/add"]
    assert report["removed_paths"] == ["/api/v1/remove"]
    assert report["summary"]["changed_path_count"] == 1
    assert report["summary"]["added_schema_count"] == 1
    assert report["summary"]["removed_schema_count"] == 1
    assert report["changed_paths"][0]["path"] == "/api/v1/example"
    assert report["changed_paths"][0]["added_methods"] == ["post"]


def test_build_report_uses_generated_and_committed_specs(monkeypatch):
    module = _load_module()

    baseline = {
        "openapi": "3.1.0",
        "info": {"version": "1.0.0"},
        "paths": {"/api/v1/example": {"get": {"operationId": "before"}}},
        "components": {"schemas": {"Example": {"type": "object"}}},
    }
    current = {
        "openapi": "3.1.0",
        "info": {"version": "1.0.1"},
        "paths": {"/api/v1/example": {"get": {"operationId": "after"}}},
        "components": {"schemas": {"Example": {"type": "object"}}},
    }

    monkeypatch.setattr(module, "load_committed_spec", lambda: baseline)
    monkeypatch.setattr(module, "generate_current_spec", lambda: current)

    report = module.build_report()

    assert report["openapi_path"] == "backend/openapi.json"
    assert report["openapi_version"] == "3.1.0"
    assert report["info_version"] == "1.0.1"
    assert report["changed"] is True
    assert report["summary"]["changed_path_count"] == 1
