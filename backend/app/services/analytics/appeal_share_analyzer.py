"""Compute appeal share analytics from angle_facts.

Provides distribution analysis and time-series trends for creative appeal types
(hook types, offer types, proof types, creative styles, LP patterns, pain points).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import select, func, extract, and_
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.brand_registry import AngleFact

logger = logging.getLogger(__name__)


def _flatten_jsonb_list(value: Any) -> list[str]:
    """Safely extract strings from a JSONB array field.

    Handles: None, list of strings like ["初回限定", "割引"], mixed types.
    """
    if not value:
        return []
    if not isinstance(value, list):
        return [str(value)] if value else []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif item is not None:
            s = str(item).strip()
            if s:
                result.append(s)
    return result


def _build_distribution(counter: Counter) -> list[dict]:
    """Convert a Counter into a sorted distribution list with share values."""
    total = sum(counter.values())
    if total == 0:
        return []
    items = []
    for label, count in counter.most_common():
        items.append({
            "type": label,
            "count": count,
            "share": round(count / total, 4),
        })
    return items


def _apply_filters(
    stmt,
    genre: str | None = None,
    date_from: datetime | str | None = None,
    date_to: datetime | str | None = None,
):
    """Apply genre and date filters to an AngleFact query via joined Ad."""
    conditions = []

    if genre:
        conditions.append(Ad.category == genre)

    if date_from:
        if isinstance(date_from, str):
            date_from = datetime.fromisoformat(date_from)
        conditions.append(Ad.created_at >= date_from)

    if date_to:
        if isinstance(date_to, str):
            date_to = datetime.fromisoformat(date_to)
        conditions.append(Ad.created_at <= date_to)

    if conditions:
        stmt = stmt.join(Ad, AngleFact.ad_id == Ad.id).where(and_(*conditions))

    return stmt


def compute_appeal_share(
    session: Session,
    genre: str | None = None,
    date_from: datetime | str | None = None,
    date_to: datetime | str | None = None,
) -> dict:
    """Compute appeal share distribution across all angle_facts.

    Returns:
    {
        "hook_type_distribution": [{"type": "question", "count": 50, "share": 0.25}, ...],
        "offer_type_distribution": [...],
        "proof_type_distribution": [...],
        "creative_style_distribution": [...],
        "lp_pattern_distribution": [...],
        "pain_point_distribution": [...],
        "cross_tab": {"hook_x_offer": {}, "hook_x_proof": {}},
        "total_facts": int,
        "filters": {"genre": genre, "date_from": str, "date_to": str}
    }
    """
    stmt = select(AngleFact)
    stmt = _apply_filters(stmt, genre, date_from, date_to)
    facts = session.scalars(stmt).all()

    hook_counter: Counter = Counter()
    offer_counter: Counter = Counter()
    proof_counter: Counter = Counter()
    style_counter: Counter = Counter()
    lp_pattern_counter: Counter = Counter()
    pain_counter: Counter = Counter()

    # Cross-tab accumulators
    hook_x_offer: dict[str, Counter] = defaultdict(Counter)
    hook_x_proof: dict[str, Counter] = defaultdict(Counter)

    for fact in facts:
        # Hook type (single value)
        if fact.hook_type:
            hook_counter[fact.hook_type] += 1

        # JSONB array fields
        offers = _flatten_jsonb_list(fact.offer_types)
        for o in offers:
            offer_counter[o] += 1

        proofs = _flatten_jsonb_list(fact.proof_types)
        for p in proofs:
            proof_counter[p] += 1

        styles = _flatten_jsonb_list(fact.creative_styles)
        for s in styles:
            style_counter[s] += 1

        pains = _flatten_jsonb_list(fact.pain_points)
        for p in pains:
            pain_counter[p] += 1

        # LP pattern (single value)
        if fact.lp_pattern:
            lp_pattern_counter[fact.lp_pattern] += 1

        # Cross-tabs: hook_type x offer_types, hook_type x proof_types
        if fact.hook_type:
            for o in offers:
                hook_x_offer[fact.hook_type][o] += 1
            for p in proofs:
                hook_x_proof[fact.hook_type][p] += 1

    # Serialize cross-tabs
    cross_tab = {
        "hook_x_offer": {
            hook: dict(offer_counts.most_common())
            for hook, offer_counts in sorted(hook_x_offer.items())
        },
        "hook_x_proof": {
            hook: dict(proof_counts.most_common())
            for hook, proof_counts in sorted(hook_x_proof.items())
        },
    }

    return {
        "hook_type_distribution": _build_distribution(hook_counter),
        "offer_type_distribution": _build_distribution(offer_counter),
        "proof_type_distribution": _build_distribution(proof_counter),
        "creative_style_distribution": _build_distribution(style_counter),
        "lp_pattern_distribution": _build_distribution(lp_pattern_counter),
        "pain_point_distribution": _build_distribution(pain_counter),
        "cross_tab": cross_tab,
        "total_facts": len(facts),
        "filters": {
            "genre": genre,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
        },
    }


def compute_monthly_trends(
    session: Session,
    months: int = 6,
    genre: str | None = None,
) -> dict:
    """Compute monthly time series for appeal types.

    Returns:
    {
        "months": ["2025-10", "2025-11", ...],
        "hook_type_trends": {"question": [10, 15, ...], ...},
        "offer_type_trends": {...},
        "total_per_month": [100, 120, ...]
    }
    """
    now = datetime.now(timezone.utc)
    start_date = now - relativedelta(months=months)

    # Load angle facts with their ad's created_at
    stmt = (
        select(AngleFact, Ad.created_at)
        .join(Ad, AngleFact.ad_id == Ad.id)
        .where(Ad.created_at >= start_date)
    )
    if genre:
        stmt = stmt.where(Ad.category == genre)

    rows = session.execute(stmt).all()

    # Build month labels
    month_labels: list[str] = []
    cursor = start_date.replace(day=1)
    end = now.replace(day=1)
    while cursor <= end:
        month_labels.append(cursor.strftime("%Y-%m"))
        cursor += relativedelta(months=1)

    # Initialize accumulators
    hook_trends: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    offer_trends: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_per_month: dict[str, int] = defaultdict(int)

    for fact, created_at in rows:
        if created_at is None:
            continue
        month_key = created_at.strftime("%Y-%m")
        if month_key not in month_labels:
            continue

        total_per_month[month_key] += 1

        # Hook type trends
        if fact.hook_type:
            hook_trends[fact.hook_type][month_key] += 1

        # Offer type trends
        for offer in _flatten_jsonb_list(fact.offer_types):
            offer_trends[offer][month_key] += 1

    # Convert to ordered lists matching month_labels
    def _to_series(trend_dict: dict[str, dict[str, int]]) -> dict[str, list[int]]:
        result = {}
        for label, month_counts in sorted(trend_dict.items()):
            result[label] = [month_counts.get(m, 0) for m in month_labels]
        return result

    return {
        "months": month_labels,
        "hook_type_trends": _to_series(hook_trends),
        "offer_type_trends": _to_series(offer_trends),
        "total_per_month": [total_per_month.get(m, 0) for m in month_labels],
    }
