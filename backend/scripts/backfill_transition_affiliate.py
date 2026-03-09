"""DPRO-DATA-001: Backfill transition_type / is_affiliate metadata.

This script fills missing DPro-related metadata fields with conservative heuristics.
It only writes values when they can be inferred with reasonable confidence.

Usage:
    python -m scripts.backfill_transition_affiliate              # dry-run
    python -m scripts.backfill_transition_affiliate --execute    # apply changes
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


_AFFILIATE_HINTS = ("affiliate", "aff", "afid", "ref=", "utm_source=affiliate", "utm_medium=affiliate")
_PR_HINTS = ("pr", "official", "brand")
_DOMAIN_MIN_SAMPLES = 3
_DOMAIN_PURITY = 0.85


def _normalize_transition(raw: str | None) -> str | None:
    if not raw:
        return None
    t = str(raw).strip().lower()
    if not t:
        return None
    if t in ("survey_lp", "survey", "questionnaire", "questionnaire_lp", "enquete", "アンケートlp"):
        return "survey_lp"
    if t in ("manga_lp", "manga", "comic_lp", "漫画lp", "漫画記事lp"):
        return "manga_lp"
    if t in ("article_lp", "article", "lp", "landing_page", "landing"):
        return "article_lp"
    if t in ("other", "unknown"):
        return "other"
    return None


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower().strip()
    except Exception:
        return None
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _infer_transition_type(ad: Ad) -> tuple[str | None, str | None, float]:
    meta = ad.ad_metadata or {}

    existing = _normalize_transition(meta.get("transition_type") if isinstance(meta, dict) else None)
    if existing:
        return existing, "existing_metadata", 1.0

    source_parts = [
        meta.get("destination_type") if isinstance(meta, dict) else None,
        meta.get("landing_page_type") if isinstance(meta, dict) else None,
        ad.destination_url,
    ]
    source = " ".join([str(x) for x in source_parts if x]).lower()
    if not source:
        return None, None, 0.0

    if any(k in source for k in ("survey", "questionnaire", "enquete", "アンケート")):
        return "survey_lp", "keyword_heuristic", 0.78
    if any(k in source for k in ("manga", "comic", "漫画")):
        return "manga_lp", "keyword_heuristic", 0.78
    if any(k in source for k in ("article", "lp", "landing")):
        return "article_lp", "keyword_heuristic", 0.72
    return "other", "keyword_heuristic", 0.6


def _parse_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        t = value.strip().lower()
        if t in ("true", "1", "yes", "y"):
            return True
        if t in ("false", "0", "no", "n"):
            return False
    return None


def _infer_is_affiliate(ad: Ad) -> tuple[bool | None, str | None, float]:
    meta = ad.ad_metadata or {}

    if isinstance(meta, dict):
        for key in ("is_affiliate", "affiliate", "affiliate_product", "is_affiliate_product"):
            parsed = _parse_bool(meta.get(key))
            if parsed is not None:
                return parsed, "existing_metadata", 1.0

    url = (ad.destination_url or "").lower()
    if url:
        if any(h in url for h in _AFFILIATE_HINTS):
            return True, "url_affiliate_hint", 0.82
        query_part = url.split("?", 1)[1] if "?" in url else ""
        if query_part:
            keys = [seg.split("=")[0].strip() for seg in query_part.split("&") if seg.strip()]
            if any(re.fullmatch(r"(aff|afid|affiliate|ref)", key) for key in keys):
                return True, "url_query_key", 0.88
        if any(h in url for h in _PR_HINTS):
            return False, "url_pr_hint", 0.7

    return None, None, 0.0


def _build_domain_priors(ads: list[Ad]) -> tuple[dict[str, str], dict[str, bool]]:
    transition_by_domain: dict[str, Counter] = defaultdict(Counter)
    affiliate_by_domain: dict[str, Counter] = defaultdict(Counter)

    for ad in ads:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        domain = _extract_domain(ad.destination_url)
        if not domain:
            continue

        tr = _normalize_transition(meta.get("transition_type"))
        if tr:
            transition_by_domain[domain][tr] += 1

        aff = _parse_bool(meta.get("is_affiliate"))
        if aff is not None:
            affiliate_by_domain[domain][bool(aff)] += 1

    transition_prior: dict[str, str] = {}
    for domain, counts in transition_by_domain.items():
        total = sum(counts.values())
        if total < _DOMAIN_MIN_SAMPLES:
            continue
        top_label, top_count = counts.most_common(1)[0]
        if (top_count / total) >= _DOMAIN_PURITY:
            transition_prior[domain] = top_label

    affiliate_prior: dict[str, bool] = {}
    for domain, counts in affiliate_by_domain.items():
        total = sum(counts.values())
        if total < _DOMAIN_MIN_SAMPLES:
            continue
        top_label, top_count = counts.most_common(1)[0]
        if (top_count / total) >= _DOMAIN_PURITY:
            affiliate_prior[domain] = bool(top_label)

    return transition_prior, affiliate_prior


def backfill_metadata(
    session,
    execute: bool = False,
    fill_affiliate_default_false: bool = False,
    fill_transition_default_other: bool = False,
    annotate_existing_inference: bool = False,
) -> dict:
    ads = session.query(Ad).order_by(Ad.id).all()
    total_ads = len(ads)
    transition_prior, affiliate_prior = _build_domain_priors(ads)

    transition_updated = 0
    transition_updated_from_domain = 0
    affiliate_updated = 0
    affiliate_updated_from_domain = 0
    affiliate_defaulted_false = 0
    transition_defaulted_other = 0
    transition_annotated_existing = 0
    unresolved_transition = 0
    unresolved_affiliate = 0
    affiliate_annotated_existing = 0

    for ad in ads:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        dirty = False
        domain = _extract_domain(ad.destination_url)

        if annotate_existing_inference:
            tr_raw = meta.get("transition_type")
            tr_norm = _normalize_transition(tr_raw if isinstance(tr_raw, str) else None)
            if tr_norm and ("transition_type_inference_source" not in meta or "transition_type_confidence" not in meta):
                meta["transition_type"] = tr_norm
                meta.setdefault("transition_type_inference_source", "preexisting_value")
                meta.setdefault("transition_type_confidence", 0.5)
                transition_annotated_existing += 1
                dirty = True

            if meta.get("is_affiliate") is not None and (
                "is_affiliate_inference_source" not in meta or "is_affiliate_confidence" not in meta
            ):
                parsed_existing = _parse_bool(meta.get("is_affiliate"))
                if parsed_existing is not None:
                    meta["is_affiliate"] = bool(parsed_existing)
                    meta.setdefault("is_affiliate_inference_source", "preexisting_value")
                    meta.setdefault("is_affiliate_confidence", 0.5)
                    affiliate_annotated_existing += 1
                    dirty = True

        if not isinstance(meta.get("transition_type"), str) or not str(meta.get("transition_type")).strip():
            inferred_transition, transition_source, transition_confidence = _infer_transition_type(ad)
            used_domain_prior = False
            if not inferred_transition and domain and domain in transition_prior:
                inferred_transition = transition_prior[domain]
                used_domain_prior = True
                transition_source = "domain_prior"
                transition_confidence = 0.65
            if not inferred_transition and fill_transition_default_other:
                inferred_transition = "other"
                transition_defaulted_other += 1
                transition_source = "default_other_fallback"
                transition_confidence = 0.3

            if inferred_transition:
                meta["transition_type"] = inferred_transition
                meta["transition_type_inference_source"] = transition_source or "unknown"
                meta["transition_type_confidence"] = round(float(transition_confidence), 2)
                transition_updated += 1
                if used_domain_prior:
                    transition_updated_from_domain += 1
                dirty = True
            else:
                unresolved_transition += 1

        if meta.get("is_affiliate") is None:
            inferred_affiliate, affiliate_source, affiliate_confidence = _infer_is_affiliate(ad)
            used_domain_prior = False
            used_default = False
            if inferred_affiliate is None and domain and domain in affiliate_prior:
                inferred_affiliate = affiliate_prior[domain]
                used_domain_prior = True
                affiliate_source = "domain_prior"
                affiliate_confidence = 0.6
            if inferred_affiliate is None and fill_affiliate_default_false:
                inferred_affiliate = False
                used_default = True
                affiliate_source = "default_false_fallback"
                affiliate_confidence = 0.25

            if inferred_affiliate is not None:
                meta["is_affiliate"] = bool(inferred_affiliate)
                meta["is_affiliate_inference_source"] = affiliate_source or "unknown"
                meta["is_affiliate_confidence"] = round(float(affiliate_confidence), 2)
                affiliate_updated += 1
                if used_domain_prior:
                    affiliate_updated_from_domain += 1
                if used_default:
                    affiliate_defaulted_false += 1
                dirty = True
            else:
                unresolved_affiliate += 1

        if dirty and execute:
            ad.ad_metadata = meta

    if execute:
        session.commit()

    return {
        "total_ads": total_ads,
        "transition_updated": transition_updated,
        "transition_updated_from_domain": transition_updated_from_domain,
        "affiliate_updated": affiliate_updated,
        "affiliate_updated_from_domain": affiliate_updated_from_domain,
        "affiliate_defaulted_false": affiliate_defaulted_false,
        "transition_defaulted_other": transition_defaulted_other,
        "transition_annotated_existing": transition_annotated_existing,
        "unresolved_transition": unresolved_transition,
        "unresolved_affiliate": unresolved_affiliate,
        "affiliate_annotated_existing": affiliate_annotated_existing,
        "domain_transition_priors": len(transition_prior),
        "domain_affiliate_priors": len(affiliate_prior),
        "fill_affiliate_default_false": fill_affiliate_default_false,
        "fill_transition_default_other": fill_transition_default_other,
        "annotate_existing_inference": annotate_existing_inference,
        "executed": execute,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill transition_type/is_affiliate metadata")
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument(
        "--fill-affiliate-default-false",
        action="store_true",
        help="When still unknown, set is_affiliate=false as a final fallback",
    )
    parser.add_argument(
        "--fill-transition-default-other",
        action="store_true",
        help="When still unknown, set transition_type=other as a final fallback",
    )
    parser.add_argument(
        "--annotate-existing-inference",
        action="store_true",
        help="Add inference source/confidence fields for rows that already have transition_type/is_affiliate",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  DPRO-DATA-001: transition_type/is_affiliate backfill")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        result = backfill_metadata(
            session,
            execute=args.execute,
            fill_affiliate_default_false=args.fill_affiliate_default_false,
            fill_transition_default_other=args.fill_transition_default_other,
            annotate_existing_inference=args.annotate_existing_inference,
        )
        print(f"\n  Total ads scanned:        {result['total_ads']}")
        print(f"  transition priors:        {result['domain_transition_priors']}")
        print(f"  affiliate priors:         {result['domain_affiliate_priors']}")
        print(f"  transition_type updated:  {result['transition_updated']}")
        print(f"    existing annotated:     {result['transition_annotated_existing']}")
        print(f"    via domain priors:      {result['transition_updated_from_domain']}")
        print(f"    via default other:      {result['transition_defaulted_other']}")
        print(f"  is_affiliate updated:     {result['affiliate_updated']}")
        print(f"    existing annotated:     {result['affiliate_annotated_existing']}")
        print(f"    via domain priors:      {result['affiliate_updated_from_domain']}")
        print(f"    via default false:      {result['affiliate_defaulted_false']}")
        print(f"  transition unresolved:    {result['unresolved_transition']}")
        print(f"  affiliate unresolved:     {result['unresolved_affiliate']}")
        if not args.execute:
            print("\n  DRY-RUN. Use --execute to apply changes.")
        else:
            print("\n  Changes committed.")
        print()
    except Exception as e:
        session.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
