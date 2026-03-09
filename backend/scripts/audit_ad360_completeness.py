"""Audit Ad360 completeness and queue low-completeness ads for reprocess."""

from __future__ import annotations

import argparse
import json

from app.core.database import SyncSessionLocal
from app.services.ad360_unification import audit_ad360_completeness


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Ad360 completeness")
    parser.add_argument("--threshold", type=float, default=0.8)
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        report = audit_ad360_completeness(session, threshold=float(args.threshold))
        session.commit()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
