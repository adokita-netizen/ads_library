#!/usr/bin/env python3
"""Compute genre benchmarks (percentiles) for key metrics.

Outputs: backend/exports/genre_benchmarks.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/compute_benchmarks.py
"""

import json, math, os, sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

def pctl(sv, p):
    if not sv: return 0.0
    n = len(sv)
    if n == 1: return sv[0]
    k = (p / 100.0) * (n - 1)
    lo = int(math.floor(k)); hi = min(lo + 1, n - 1)
    return sv[lo] + (k - lo) * (sv[hi] - sv[lo])

def stats(vals):
    if not vals: return {"median": 0, "p25": 0, "p75": 0, "p90": 0, "mean": 0, "count": 0}
    s = sorted(vals)
    return {"median": round(pctl(s, 50), 1), "p25": round(pctl(s, 25), 1),
            "p75": round(pctl(s, 75), 1), "p90": round(pctl(s, 90), 1),
            "mean": round(sum(vals)/len(vals), 1), "count": len(vals)}

def _score(ad):
    try: return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except: return 0.0
def _views(ad):
    rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
    v = rm.get("total_views", 0) or 0
    return float(v or ad.view_count or 0)
def _likes(ad): return float(ad.like_count or 0)
def _spend(ad):
    rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
    return float(rm.get("total_spend_jpy", 0) or 0)
def _longevity(ad): return float((ad.ad_metadata or {}).get("days_running", 1) or 1)
def _genre(ad):
    g = (ad.ad_metadata or {}).get("fine_genre_en", "")
    if g: return g.lower()
    return ad.category.value if ad.category else "other"

MF = {"hit_score": _score, "view_count": _views, "like_count": _likes,
      "spend": _spend, "longevity_days": _longevity}

def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print("Total ads: %d" % len(ads))
        by_g = defaultdict(list)
        for ad in ads: by_g[_genre(ad)].append(ad)
        print("Genres: %d" % len(by_g))
        result = {"generated_at": datetime.now(timezone.utc).isoformat(),
                  "total_ads": len(ads), "genre_count": len(by_g), "benchmarks": {}}
        for genre in sorted(by_g):
            result["benchmarks"][genre] = {}
            for mn, fn in MF.items():
                result["benchmarks"][genre][mn] = stats([fn(a) for a in by_g[genre]])
        result["benchmarks"]["_all"] = {}
        for mn, fn in MF.items():
            result["benchmarks"]["_all"][mn] = stats([fn(a) for a in ads])

        print(); print("=" * 100); print("Genre Benchmarks"); print("=" * 100)
        print("%-25s %5s  %9s %9s  %10s %10s  %10s" % ("Genre", "Count", "ScP50", "ScP90", "ViewP50", "ViewP90", "SpendP50"))
        print("-" * 100)
        for genre in sorted(by_g):
            b = result["benchmarks"][genre]
            print("%-25s %5d  %9.1f %9.1f  %10.0f %10.0f  %10.0f" % (
                genre, b["hit_score"]["count"], b["hit_score"]["median"], b["hit_score"]["p90"],
                b["view_count"]["median"], b["view_count"]["p90"], b["spend"]["median"]))
        b = result["benchmarks"]["_all"]
        print("-" * 100)
        print("%-25s %5d  %9.1f %9.1f  %10.0f %10.0f  %10.0f" % (
            "ALL", b["hit_score"]["count"], b["hit_score"]["median"], b["hit_score"]["p90"],
            b["view_count"]["median"], b["view_count"]["p90"], b["spend"]["median"]))

        edir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(edir, exist_ok=True)
        op = os.path.join(edir, "genre_benchmarks.json")
        with open(op, "w", encoding="utf-8") as f: json.dump(result, f, ensure_ascii=False, indent=2)
        print("\nExported to %s" % op)
    finally: session.close()

if __name__ == "__main__": main()
