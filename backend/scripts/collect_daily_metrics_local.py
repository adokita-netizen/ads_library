#!/usr/bin/env python3
"""Persist AdDailyMetrics rows into local SQLite reliably.

Wraps app.tasks.metrics_tasks.collect_metrics_for_ads with a local SQLite session
fallback so daily metric rows are created even when the primary DB is unavailable.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.tasks.metrics_tasks import collect_metrics_for_ads


def _build_local_session():
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}")
    return sessionmaker(bind=engine)


def main() -> None:
    Session = _build_local_session()
    session = Session()
    try:
        created = collect_metrics_for_ads(session)
        session.commit()
        print(f"collect_daily_metrics_local created={created}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
