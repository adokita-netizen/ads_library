#!/usr/bin/env python3
"""A/B compare two groups of ads statistically.

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/ab_compare_ads.py --group_a "genre:skincare" --group_b "genre:supplement"
"""

import argparse, json, math, os, sys
from datetime import datetime, timezone
from statistics import mean, stdev

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

def _get_score(ad):
    try: return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except: return 0.0

def _get_views(ad):
    rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
    v = rm.get("total_views", 0) or 0
    if not v: v = ad.view_count or 0
    return float(v)

def _get_spend(ad):
    rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
    return float(rm.get("total_spend_jpy", 0) or 0)

def _get_engagement(ad):
    views = _get_views(ad)
    likes = float(ad.like_count or 0)
    return (likes / views) * 100.0 if views > 0 else 0.0

METRICS = {"hit_score": _get_score, "views": _get_views, "spend_jpy": _get_spend, "engagement_rate": _get_engagement}

def filter_ads(ads, spec):
    if ":" not in spec:
        print("  [WARN] Invalid filter: %s" % spec)
        return ads
    field, value = spec.split(":", 1)
    vl = value.lower()
    result = []
    for ad in ads:
        meta = ad.ad_metadata or {}
        if field == "genre":
            if (meta.get("fine_genre_en", "") or "").lower() == vl: result.append(ad)
        elif field == "category":
            if ad.category and ad.category.value.lower() == vl: result.append(ad)
        elif field == "archetype":
            ss = meta.get("scenario_structure", {})
            if (ss.get("archetype", "") or "").lower() == vl: result.append(ad)
        elif field == "hook":
            ca = meta.get("creative_analysis", {})
            if (ca.get("hook_type", "") or "").lower() == vl: result.append(ad)
        elif field == "cta":
            ca = meta.get("creative_analysis", {})
            if (ca.get("cta_type", "") or "").lower() == vl: result.append(ad)
        elif field == "hit_level":
            if (meta.get("hit_level", "") or "").lower() == vl: result.append(ad)
    return result

def _normal_cdf(x): return 0.5 * math.erfc(-x / math.sqrt(2))

def t_test(a, b):
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2: return {"t_stat": None, "p_value": None, "df": None, "significant": None}
    m1, m2 = mean(a), mean(b)
    s1, s2 = stdev(a), stdev(b)
    se1, se2 = (s1**2)/n1, (s2**2)/n2
    se = math.sqrt(se1 + se2)
    if se == 0: return {"t_stat": 0.0, "p_value": 1.0, "df": n1+n2-2, "significant": False}
    t = (m1 - m2) / se
    num = (se1 + se2)**2
    den = (se1**2)/(n1-1) + (se2**2)/(n2-1)
    df = num/den if den > 0 else n1+n2-2
    pv = 2 * _normal_cdf(-abs(t))
    return {"t_stat": round(t, 4), "p_value": round(pv, 6), "df": round(df, 1), "significant": pv < 0.05}

def cohens_d(a, b):
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2: return None
    m1, m2 = mean(a), mean(b)
    s1, s2 = stdev(a), stdev(b)
    p = math.sqrt(((n1-1)*s1**2 + (n2-1)*s2**2) / (n1+n2-2))
    return round((m1-m2)/p, 4) if p > 0 else 0.0

def ci95(vals):
    n = len(vals)
    if n < 2: return (None, None)
    m = mean(vals); se = stdev(vals)/math.sqrt(n)
    return (round(m - 1.96*se, 2), round(m + 1.96*se, 2))

def eff_label(d):
    if d is None: return "N/A"
    a = abs(d)
    if a < 0.2: return "negligible"
    elif a < 0.5: return "small"
    elif a < 0.8: return "medium"
    return "large"

def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--group_a", required=True)
    pa.add_argument("--group_b", required=True)
    pa.add_argument("--output", default=None)
    args = pa.parse_args()
    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).all()
        print("Total ads: %d" % len(all_ads))
        ga = filter_ads(all_ads, args.group_a)
        gb = filter_ads(all_ads, args.group_b)
        print("Group A (%s): %d ads" % (args.group_a, len(ga)))
        print("Group B (%s): %d ads" % (args.group_b, len(gb)))
        if len(ga) < 2 or len(gb) < 2:
            print("[ERROR] Both groups need >= 2 ads"); return
        res = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "group_a": {"filter": args.group_a, "count": len(ga)},
               "group_b": {"filter": args.group_b, "count": len(gb)}, "metrics": {}}
        print(); print("=" * 80)
        print("A/B Comparison: %s vs %s" % (args.group_a, args.group_b))
        print("=" * 80)
        for mn, fn in METRICS.items():
            va = [fn(ad) for ad in ga]; vb = [fn(ad) for ad in gb]
            ma, mb = mean(va), mean(vb)
            ca, cb = ci95(va), ci95(vb)
            tr = t_test(va, vb); d = cohens_d(va, vb)
            res["metrics"][mn] = {
                "group_a": {"mean": round(ma, 2), "std": round(stdev(va), 2), "ci_95": list(ca), "n": len(va)},
                "group_b": {"mean": round(mb, 2), "std": round(stdev(vb), 2), "ci_95": list(cb), "n": len(vb)},
                "t_test": tr, "cohens_d": d, "effect_size": eff_label(d),
                "winner": "A" if ma > mb else ("B" if mb > ma else "tie")}
            print("\n--- %s ---" % mn)
            print("  Group A mean: %.2f  (95%% CI: %s-%s)" % (ma, ca[0], ca[1]))
            print("  Group B mean: %.2f  (95%% CI: %s-%s)" % (mb, cb[0], cb[1]))
            print("  Diff: %+.2f" % (ma - mb))
            print("  t=%s p=%s sig=%s" % (tr["t_stat"], tr["p_value"], "YES***" if tr.get("significant") else "no"))
            print("  Cohen d: %s (%s)" % (d, eff_label(d)))
            print("  Winner: %s" % ("A" if ma > mb else ("B" if mb > ma else "Tie")))
        edir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(edir, exist_ok=True)
        op = args.output or os.path.join(edir, "ab_comparison.json")
        with open(op, "w", encoding="utf-8") as f: json.dump(res, f, ensure_ascii=False, indent=2)
        print("\nExported to %s" % op)
    finally: session.close()

if __name__ == "__main__": main()
