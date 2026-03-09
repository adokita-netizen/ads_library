#!/usr/bin/env python3
"""Run the JP growth pipeline end-to-end.

This is the no-confirmation local runner for:
1. recrawl metrics
2. LP backfill
3. JP static-media recovery
4. live ingestion wave

Run from repo root:
    python backend/scripts/run_jp_growth_pipeline.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
sys.path.insert(0, BASE_DIR)


def _run(command: list[str], *, extra_env: dict[str, str] | None = None, timeout: int = 1800) -> dict:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    started = time.time()
    try:
        result = subprocess.run(
            command,
            cwd=os.path.dirname(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        elapsed = round(time.time() - started, 1)
        stdout = result.stdout or ""
        parsed_json = None
        try:
            parsed_json = json.loads(stdout)
        except Exception:
            parsed_json = None
        return {
            "cmd": command,
            "returncode": result.returncode,
            "elapsed_sec": elapsed,
            "stdout_tail": stdout.splitlines()[-20:],
            "stderr_tail": (result.stderr or "").splitlines()[-20:],
            "parsed_json": parsed_json,
        }
    except Exception as exc:
        return {
            "cmd": command,
            "returncode": -1,
            "elapsed_sec": round(time.time() - started, 1),
            "error": str(exc),
        }


def _meta_completion_summary() -> dict:
    try:
        from app.services.data_quality_report import build_meta_completion_audit
        db_path = os.path.join(BASE_DIR, "vaap_local.db")
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        try:
            return build_meta_completion_audit(session, top_n=5)["summary"]
        finally:
            session.close()
    except Exception as exc:
        return {"error": str(exc)}


def _extract_meta_scheduler_summary(steps: list[dict]) -> dict:
    for step in reversed(steps):
        parsed = step.get("parsed_json") if isinstance(step, dict) else None
        if not isinstance(parsed, dict):
            continue
        operations = parsed.get("operations_summary")
        if not isinstance(operations, dict):
            continue
        return {
            **operations,
            "mode": parsed.get("mode"),
            "meta_only": parsed.get("meta_only"),
            "policy": parsed.get("policy"),
            "meta_token": parsed.get("meta_token"),
        }
    return {}


def main() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    steps = []

    steps.append(_run([PYTHON, "backend/scripts/recrawl_metrics.py"], timeout=1200))
    steps.append(_run([PYTHON, "backend/scripts/collect_daily_metrics_local.py"], timeout=1200))
    steps.append(_run([PYTHON, "backend/scripts/backfill_landing_pages_from_metadata.py"], timeout=300))
    steps.append(_run([PYTHON, "backend/scripts/recover_jp_static_media.py"], timeout=1800))
    steps.append(_run([PYTHON, "backend/scripts/recover_meta_jp_creatives.py"], timeout=1800))
    steps.append(
        _run(
            [
                PYTHON,
                "backend/scripts/run_live_ad_ingestion_wave.py",
                "--inline",
                "--meta-only",
                "--mode",
                "nightly",
                "--keyword-limit",
                "2",
                "--limit-per-platform",
                "5",
            ],
            timeout=1800,
        )
    )

    print(
        json.dumps(
            {
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "steps": steps,
                "meta_scheduler_summary": _extract_meta_scheduler_summary(steps),
                "meta_completion_audit": _meta_completion_summary(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
