"""CI-141: Data lineage (provenance) tracking.

Records how data is transformed through the pipeline — which scripts
modify which ads, what fields changed, and when.

Stores lineage entries in ad_metadata["_lineage"] as a compact list.
Also writes to a central lineage log file for cross-ad auditing.

Usage:
    from app.core.data_lineage import record_lineage, get_lineage

    # Record a transformation
    record_lineage(
        session, ad,
        source="collect_real_metrics.py",
        action="update_metrics",
        fields_changed=["view_count", "impressions"],
        details={"api": "meta", "response_status": 200},
    )

    # Query lineage
    history = get_lineage(ad)
"""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

_LINEAGE_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "exports",
)
_LINEAGE_LOG_FILE = os.path.join(_LINEAGE_LOG_DIR, "data_lineage.jsonl")
_MAX_LINEAGE_ENTRIES = 50  # per ad, keep last N to prevent metadata bloat


def record_lineage(
    session: Session,
    ad,
    source: str,
    action: str,
    fields_changed: list[str] | None = None,
    details: dict | None = None,
    *,
    flush: bool = False,
) -> dict:
    """Record a lineage entry for an ad.

    Args:
        session: DB session (for flag_modified)
        ad: Ad model instance
        source: Script/service name (e.g., "collect_real_metrics.py")
        action: What was done (e.g., "update_metrics", "backfill_delta")
        fields_changed: List of field names that were modified
        details: Additional context dict
        flush: Whether to flush session immediately

    Returns:
        The lineage entry dict that was recorded.
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "src": source,
        "act": action,
    }
    if fields_changed:
        entry["fields"] = fields_changed
    if details:
        entry["ctx"] = details

    # Write to ad_metadata["_lineage"]
    meta = dict(ad.ad_metadata or {})
    lineage = meta.get("_lineage", [])
    lineage.append(entry)

    # Trim to prevent bloat
    if len(lineage) > _MAX_LINEAGE_ENTRIES:
        lineage = lineage[-_MAX_LINEAGE_ENTRIES:]

    meta["_lineage"] = lineage
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")

    if flush:
        session.flush()

    # Also append to central log file
    _append_to_log(ad.id, entry)

    return entry


def record_lineage_bulk(
    session: Session,
    ads: list,
    source: str,
    action: str,
    fields_changed: list[str] | None = None,
    details: dict | None = None,
):
    """Record the same lineage entry for multiple ads."""
    for ad in ads:
        record_lineage(session, ad, source, action, fields_changed, details)


def get_lineage(ad) -> list[dict]:
    """Get lineage history for an ad."""
    meta = ad.ad_metadata or {}
    return meta.get("_lineage", [])


def get_lineage_summary(ad) -> dict:
    """Get a summary of lineage for an ad."""
    lineage = get_lineage(ad)
    if not lineage:
        return {"entries": 0}

    sources = set()
    actions = set()
    all_fields = set()
    for entry in lineage:
        sources.add(entry.get("src", "unknown"))
        actions.add(entry.get("act", "unknown"))
        for f in entry.get("fields", []):
            all_fields.add(f)

    return {
        "entries": len(lineage),
        "first": lineage[0].get("ts"),
        "last": lineage[-1].get("ts"),
        "sources": sorted(sources),
        "actions": sorted(actions),
        "fields_touched": sorted(all_fields),
    }


def _append_to_log(ad_id: int, entry: dict):
    """Append a lineage entry to the central JSONL log file."""
    try:
        os.makedirs(_LINEAGE_LOG_DIR, exist_ok=True)
        log_entry = {"ad_id": ad_id, **entry}
        with open(_LINEAGE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("lineage_log_write_failed: %s", e)


def query_lineage_log(
    ad_id: int | None = None,
    source: str | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query the central lineage log file with optional filters.

    Reads from the JSONL file in reverse (newest first).
    """
    results = []
    try:
        if not os.path.exists(_LINEAGE_LOG_FILE):
            return []
        with open(_LINEAGE_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if ad_id is not None and entry.get("ad_id") != ad_id:
                continue
            if source and entry.get("src") != source:
                continue
            if action and entry.get("act") != action:
                continue

            results.append(entry)
            if len(results) >= limit:
                break
    except Exception as e:
        logger.warning("lineage_log_query_failed: %s", e)

    return results
