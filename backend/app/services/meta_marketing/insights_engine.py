"""Smart Insights Engine — data-driven analysis connecting creatives to performance metrics.

Produces structured insights: KPI summaries, trends, creative-level performance rankings,
auto-generated actionable insights ("CTR trending up 15%", "Video outperforms image 2.3x").
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select, func, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_campaign import MetaAd, MetaAdSet, MetaCampaign, MetaInsight

logger = structlog.get_logger()


class InsightsEngine:
    """Analyze synced Meta data and produce structured, actionable insights."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Performance Summary ──────────────────────────────────────

    async def get_performance_summary(
        self,
        account_id: str,
        days: int = 7,
    ) -> dict:
        """KPI summary with period-over-period comparison.

        Returns current period metrics, previous period metrics, and delta percentages.
        """
        now = datetime.now(timezone.utc)
        current_start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        previous_start = (now - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        current_end = now.strftime("%Y-%m-%d")

        async def _aggregate(date_from: str, date_to: str) -> dict:
            result = await self.db.execute(
                select(
                    func.sum(MetaInsight.impressions).label("impressions"),
                    func.sum(MetaInsight.reach).label("reach"),
                    func.sum(MetaInsight.clicks).label("clicks"),
                    func.sum(MetaInsight.spend).label("spend"),
                    func.sum(MetaInsight.conversions).label("conversions"),
                    func.sum(MetaInsight.conversion_values).label("conversion_values"),
                    func.avg(MetaInsight.frequency).label("avg_frequency"),
                )
                .where(
                    MetaInsight.account_id == account_id,
                    MetaInsight.date_start >= date_from,
                    MetaInsight.date_start < date_to,
                )
            )
            row = result.one()
            impressions = int(row.impressions or 0)
            clicks = int(row.clicks or 0)
            spend = float(row.spend or 0)
            conversions = int(row.conversions or 0)
            conversion_values = float(row.conversion_values or 0)

            return {
                "impressions": impressions,
                "reach": int(row.reach or 0),
                "clicks": clicks,
                "spend": round(spend, 2),
                "conversions": conversions,
                "conversion_values": round(conversion_values, 2),
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0,
                "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
                "cpm": round(spend / impressions * 1000, 2) if impressions > 0 else 0,
                "cpa": round(spend / conversions, 2) if conversions > 0 else 0,
                "roas": round(conversion_values / spend, 2) if spend > 0 else 0,
                "avg_frequency": round(float(row.avg_frequency or 0), 2),
            }

        current = await _aggregate(current_start, current_end)
        previous = await _aggregate(previous_start, current_start)

        logger.info("performance_summary", account_id=account_id, days=days,
                     impressions=current["impressions"], spend=current["spend"])

        # Calculate deltas
        def _delta(curr_val: float, prev_val: float) -> Optional[float]:
            if prev_val == 0:
                return None
            return round((curr_val - prev_val) / prev_val * 100, 1)

        deltas = {}
        for key in current:
            deltas[key] = _delta(current[key], previous[key])

        return {
            "account_id": account_id,
            "period_days": days,
            "current_period": current,
            "previous_period": previous,
            "deltas": deltas,
        }

    # ── Daily Trends ─────────────────────────────────────────────

    async def get_daily_trends(
        self,
        account_id: str,
        days: int = 30,
        entity_type: Optional[str] = None,
    ) -> dict:
        """Daily aggregated metrics for trend visualization."""
        date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        query = (
            select(
                MetaInsight.date_start,
                func.sum(MetaInsight.impressions).label("impressions"),
                func.sum(MetaInsight.clicks).label("clicks"),
                func.sum(MetaInsight.spend).label("spend"),
                func.sum(MetaInsight.conversions).label("conversions"),
                func.sum(MetaInsight.conversion_values).label("conversion_values"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.date_start >= date_from,
            )
            .group_by(MetaInsight.date_start)
            .order_by(MetaInsight.date_start)
        )
        if entity_type:
            query = query.where(MetaInsight.entity_type == entity_type)

        result = await self.db.execute(query)
        rows = result.all()

        trends = []
        for row in rows:
            imp = int(row.impressions or 0)
            clk = int(row.clicks or 0)
            spd = float(row.spend or 0)
            conv = int(row.conversions or 0)
            trends.append({
                "date": row.date_start,
                "impressions": imp,
                "clicks": clk,
                "spend": round(spd, 2),
                "conversions": conv,
                "ctr": round(clk / imp * 100, 2) if imp > 0 else 0,
                "cpc": round(spd / clk, 2) if clk > 0 else 0,
                "cpa": round(spd / conv, 2) if conv > 0 else 0,
            })

        return {"account_id": account_id, "days": days, "trends": trends}

    # ── Creative Performance Rankings ────────────────────────────

    async def get_creative_performance(
        self,
        account_id: str,
        days: int = 7,
        sort_by: str = "spend",
    ) -> dict:
        """Join MetaAd creative data with MetaInsight metrics.

        Returns each ad with its creative attributes AND performance numbers side-by-side.
        """
        date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        # Get performance per ad
        perf_query = (
            select(
                MetaInsight.entity_id,
                func.sum(MetaInsight.impressions).label("impressions"),
                func.sum(MetaInsight.clicks).label("clicks"),
                func.sum(MetaInsight.spend).label("spend"),
                func.sum(MetaInsight.conversions).label("conversions"),
                func.sum(MetaInsight.conversion_values).label("conversion_values"),
                func.sum(MetaInsight.video_thruplay).label("video_thruplay"),
                func.sum(MetaInsight.video_p25_watched).label("video_p25"),
                func.sum(MetaInsight.video_p50_watched).label("video_p50"),
                func.sum(MetaInsight.video_p75_watched).label("video_p75"),
                func.sum(MetaInsight.video_p100_watched).label("video_p100"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
                MetaInsight.date_start >= date_from,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.impressions) > 0)
        )

        perf_result = await self.db.execute(perf_query)
        perf_rows = {row.entity_id: row for row in perf_result.all()}

        if not perf_rows:
            logger.info("creative_performance_empty", account_id=account_id, days=days)
            return {"account_id": account_id, "ads": [], "type_summary": {}}

        # Get ad creative data
        ad_result = await self.db.execute(
            select(MetaAd).where(
                MetaAd.account_id == account_id,
                MetaAd.meta_id.in_(list(perf_rows.keys())),
            )
        )
        ads = ad_result.scalars().all()

        # Combine creative + performance
        combined = []
        for ad in ads:
            perf = perf_rows.get(ad.meta_id)
            if not perf:
                continue

            imp = int(perf.impressions or 0)
            clk = int(perf.clicks or 0)
            spd = float(perf.spend or 0)
            conv = int(perf.conversions or 0)
            conv_val = float(perf.conversion_values or 0)
            thruplay = int(perf.video_thruplay or 0)
            p25 = int(perf.video_p25 or 0)
            p50 = int(perf.video_p50 or 0)
            p75 = int(perf.video_p75 or 0)
            p100 = int(perf.video_p100 or 0)

            entry = {
                # Creative attributes
                "meta_id": ad.meta_id,
                "name": ad.name,
                "status": ad.effective_status,
                "creative_type": ad.creative_type or "unknown",
                "creative_title": ad.creative_title,
                "creative_body": ad.creative_body,
                "creative_thumbnail_url": ad.creative_thumbnail_url,
                "creative_image_url": ad.creative_image_url,
                "creative_video_url": ad.creative_video_url,
                # Performance metrics
                "impressions": imp,
                "clicks": clk,
                "spend": round(spd, 2),
                "conversions": conv,
                "conversion_values": round(conv_val, 2),
                "ctr": round(clk / imp * 100, 2) if imp > 0 else 0,
                "cpc": round(spd / clk, 2) if clk > 0 else 0,
                "cpm": round(spd / imp * 1000, 2) if imp > 0 else 0,
                "cpa": round(spd / conv, 2) if conv > 0 else 0,
                "roas": round(conv_val / spd, 2) if spd > 0 else 0,
                # Video metrics (null for non-video)
                "video_thruplay": thruplay if thruplay > 0 else None,
                "video_completion_rate": round(p100 / imp * 100, 2) if imp > 0 and p100 > 0 else None,
                "video_retention": {
                    "p25": p25,
                    "p50": p50,
                    "p75": p75,
                    "p100": p100,
                } if p25 > 0 else None,
            }
            combined.append(entry)

        # Sort
        sort_key = sort_by if sort_by in ("spend", "ctr", "cpc", "cpa", "impressions", "conversions", "roas") else "spend"
        reverse = sort_key not in ("cpc", "cpa")  # Lower is better for CPC/CPA
        combined.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=reverse)

        # Aggregate by creative type
        type_summary = {}
        for item in combined:
            ct = item["creative_type"]
            if ct not in type_summary:
                type_summary[ct] = {
                    "count": 0, "impressions": 0, "clicks": 0,
                    "spend": 0, "conversions": 0,
                }
            ts = type_summary[ct]
            ts["count"] += 1
            ts["impressions"] += item["impressions"]
            ts["clicks"] += item["clicks"]
            ts["spend"] += item["spend"]
            ts["conversions"] += item["conversions"]

        for ct, ts in type_summary.items():
            ts["avg_ctr"] = round(ts["clicks"] / ts["impressions"] * 100, 2) if ts["impressions"] > 0 else 0
            ts["avg_cpc"] = round(ts["spend"] / ts["clicks"], 2) if ts["clicks"] > 0 else 0
            ts["avg_cpa"] = round(ts["spend"] / ts["conversions"], 2) if ts["conversions"] > 0 else 0

        return {
            "account_id": account_id,
            "period_days": days,
            "ads": combined,
            "type_summary": type_summary,
        }

    # ── Smart Insights Generator ────────────────────────────────

    async def generate_smart_insights(self, account_id: str) -> list[dict]:
        """Analyze all available data and auto-generate actionable insights.

        Each insight has: category, severity, title, description, metric, value.
        """
        insights = []
        now = datetime.now(timezone.utc)

        # 1. CTR trend (7-day vs previous 7-day)
        summary = await self.get_performance_summary(account_id, days=7)
        curr = summary["current_period"]
        deltas = summary["deltas"]

        if curr["impressions"] > 100:
            ctr_delta = deltas.get("ctr")
            if ctr_delta is not None:
                if ctr_delta > 10:
                    insights.append({
                        "category": "trend",
                        "severity": "positive",
                        "title": f"CTRが先週比{ctr_delta:+.1f}%上昇中",
                        "description": f"現在のCTRは{curr['ctr']}%で、前の7日間から改善しています。好調なクリエイティブを特定してスケールを検討してください。",
                        "metric": "ctr",
                        "value": curr["ctr"],
                        "delta": ctr_delta,
                    })
                elif ctr_delta < -10:
                    insights.append({
                        "category": "trend",
                        "severity": "negative",
                        "title": f"CTRが先週比{ctr_delta:+.1f}%低下",
                        "description": f"現在のCTRは{curr['ctr']}%で、前の7日間から低下しています。クリエイティブの疲労やオーディエンスの飽和が原因の可能性があります。",
                        "metric": "ctr",
                        "value": curr["ctr"],
                        "delta": ctr_delta,
                    })

            # CPA trend
            cpa_delta = deltas.get("cpa")
            if cpa_delta is not None and curr["conversions"] > 0:
                if cpa_delta > 20:
                    insights.append({
                        "category": "cost",
                        "severity": "negative",
                        "title": f"CPAが先週比{cpa_delta:+.1f}%上昇 (¥{curr['cpa']:,.0f})",
                        "description": "獲得コストが増加しています。非効率な広告セットの予算削減またはターゲティング見直しを検討してください。",
                        "metric": "cpa",
                        "value": curr["cpa"],
                        "delta": cpa_delta,
                    })
                elif cpa_delta < -15:
                    insights.append({
                        "category": "cost",
                        "severity": "positive",
                        "title": f"CPAが先週比{cpa_delta:+.1f}%改善 (¥{curr['cpa']:,.0f})",
                        "description": "獲得コストが改善しています。好調な広告セットへの予算増額でさらなるスケールが期待できます。",
                        "metric": "cpa",
                        "value": curr["cpa"],
                        "delta": cpa_delta,
                    })

            # ROAS
            if curr["roas"] > 0:
                roas_delta = deltas.get("roas")
                if roas_delta is not None and roas_delta > 15:
                    insights.append({
                        "category": "revenue",
                        "severity": "positive",
                        "title": f"ROASが{curr['roas']:.1f}xに改善",
                        "description": f"広告投資効率が向上しています（先週比{roas_delta:+.1f}%）。高ROASキャンペーンへの集中投資を検討してください。",
                        "metric": "roas",
                        "value": curr["roas"],
                        "delta": roas_delta,
                    })

            # Spend without conversions
            if curr["spend"] > 5000 and curr["conversions"] == 0:
                insights.append({
                    "category": "alert",
                    "severity": "critical",
                    "title": f"¥{curr['spend']:,.0f}消化でコンバージョン0件",
                    "description": "過去7日間で広告費を消化していますがコンバージョンが発生していません。コンバージョン計測設定またはランディングページを確認してください。",
                    "metric": "conversions",
                    "value": 0,
                    "delta": None,
                })

        # 2. Creative type comparison
        creative_perf = await self.get_creative_performance(account_id, days=14, sort_by="ctr")
        type_summary = creative_perf.get("type_summary", {})

        if len(type_summary) >= 2:
            sorted_types = sorted(type_summary.items(), key=lambda x: x[1].get("avg_ctr", 0), reverse=True)
            best_type = sorted_types[0]
            worst_type = sorted_types[-1]

            if best_type[1]["avg_ctr"] > 0 and worst_type[1]["avg_ctr"] > 0:
                ratio = best_type[1]["avg_ctr"] / worst_type[1]["avg_ctr"]
                if ratio > 1.5:
                    insights.append({
                        "category": "creative",
                        "severity": "positive",
                        "title": f"{best_type[0]}が{worst_type[0]}より{ratio:.1f}倍高いCTR",
                        "description": f"{best_type[0]}の平均CTRは{best_type[1]['avg_ctr']}%、{worst_type[0]}は{worst_type[1]['avg_ctr']}%です。{best_type[0]}形式のクリエイティブを増やすことを推奨します。",
                        "metric": "ctr_by_type",
                        "value": ratio,
                        "delta": None,
                    })

        # 3. Top performer identification
        ads = creative_perf.get("ads", [])
        if len(ads) >= 3:
            top_ad = ads[0]  # Already sorted by CTR
            if top_ad["ctr"] > 0:
                avg_ctr = sum(a["ctr"] for a in ads) / len(ads) if ads else 0
                if top_ad["ctr"] > avg_ctr * 1.5 and top_ad["impressions"] > 500:
                    insights.append({
                        "category": "creative",
                        "severity": "positive",
                        "title": f"トップパフォーマー: CTR {top_ad['ctr']}%",
                        "description": f"「{top_ad['name'][:40]}」のCTRは平均({avg_ctr:.2f}%)の{top_ad['ctr']/avg_ctr:.1f}倍です。このクリエイティブのスケールを検討してください。",
                        "metric": "top_ctr",
                        "value": top_ad["ctr"],
                        "delta": None,
                    })

        # 4. Frequency warning
        if curr.get("avg_frequency", 0) > 3:
            insights.append({
                "category": "audience",
                "severity": "warning",
                "title": f"フリークエンシーが{curr['avg_frequency']:.1f}に到達",
                "description": "同一ユーザーへの広告表示回数が高くなっています。ターゲティング拡大または新規オーディエンスの追加を検討してください。",
                "metric": "frequency",
                "value": curr["avg_frequency"],
                "delta": None,
            })

        # 5. Creative portfolio health check
        active_ads = [a for a in ads if a.get("status") == "ACTIVE"]
        active_types = set(a["creative_type"] for a in active_ads)
        if len(active_ads) >= 3 and len(active_types) >= 2:
            insights.append({
                "category": "creative",
                "severity": "positive",
                "title": f"クリエイティブ充実: {len(active_ads)}件稼働中 ({len(active_types)}タイプ)",
                "description": f"アクティブなクリエイティブが{len(active_ads)}件あり、{', '.join(active_types)}の{len(active_types)}種類を運用中です。クリエイティブポートフォリオは健全です。",
                "metric": "creative_portfolio",
                "value": len(active_ads),
                "delta": None,
            })
        elif len(active_ads) > 0 and len(active_ads) < 3:
            insights.append({
                "category": "creative",
                "severity": "warning",
                "title": f"クリエイティブ不足: 稼働中{len(active_ads)}件のみ",
                "description": "アクティブなクリエイティブが少ない状態です。最低3件以上のクリエイティブを同時運用し、A/Bテストによる改善サイクルを回すことを推奨します。",
                "metric": "creative_portfolio",
                "value": len(active_ads),
                "delta": None,
            })

        # 6. Video completion insights
        video_ads = [a for a in ads if a.get("video_retention")]
        if video_ads:
            valid_completions = [a["video_completion_rate"] for a in video_ads if a.get("video_completion_rate")]
            avg_completion = sum(valid_completions) / len(valid_completions) if valid_completions else 0

            if avg_completion > 0:
                if avg_completion < 10:
                    insights.append({
                        "category": "creative",
                        "severity": "warning",
                        "title": f"動画完了率が低い ({avg_completion:.1f}%)",
                        "description": "動画を最後まで視聴するユーザーが少ない状態です。冒頭3秒のフック強化や動画尺の短縮を検討してください。",
                        "metric": "video_completion",
                        "value": avg_completion,
                        "delta": None,
                    })
                elif avg_completion > 30:
                    insights.append({
                        "category": "creative",
                        "severity": "positive",
                        "title": f"動画完了率が優秀 ({avg_completion:.1f}%)",
                        "description": "動画コンテンツの訴求力が高いです。この動画スタイルを他のクリエイティブにも展開することを推奨します。",
                        "metric": "video_completion",
                        "value": avg_completion,
                        "delta": None,
                    })

        # 7. Creative fatigue detection (CTR declining ads)
        date_14d = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        date_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # Week 1 CTR per ad
        w1_result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.sum(MetaInsight.clicks).label("clicks"),
                func.sum(MetaInsight.impressions).label("impressions"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
                MetaInsight.date_start >= date_14d,
                MetaInsight.date_start < date_7d,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.impressions) > 500)
        )
        w1_data = {}
        for row in w1_result.all():
            imp = int(row.impressions or 0)
            clk = int(row.clicks or 0)
            w1_data[row.entity_id] = clk / imp * 100 if imp > 0 else 0

        w2_result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.sum(MetaInsight.clicks).label("clicks"),
                func.sum(MetaInsight.impressions).label("impressions"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
                MetaInsight.date_start >= date_7d,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.impressions) > 500)
        )

        fatigued_count = 0
        for row in w2_result.all():
            if row.entity_id not in w1_data:
                continue
            w1_ctr = w1_data[row.entity_id]
            imp = int(row.impressions or 0)
            clk = int(row.clicks or 0)
            w2_ctr = clk / imp * 100 if imp > 0 else 0
            if w1_ctr > 0 and (w2_ctr - w1_ctr) / w1_ctr * 100 < -20:
                fatigued_count += 1

        if fatigued_count > 0:
            insights.append({
                "category": "fatigue",
                "severity": "warning",
                "title": f"{fatigued_count}件のクリエイティブで疲労兆候",
                "description": f"CTRが先週比20%以上低下しているクリエイティブが{fatigued_count}件あります。クリエイティブの更新または入れ替えを検討してください。",
                "metric": "fatigued_creatives",
                "value": fatigued_count,
                "delta": None,
            })

        # Sort: critical first, then negative, warning, positive
        severity_order = {"critical": 0, "negative": 1, "warning": 2, "positive": 3}
        insights.sort(key=lambda x: severity_order.get(x["severity"], 9))

        logger.info("smart_insights_generated", account_id=account_id, count=len(insights),
                     categories=[i["category"] for i in insights])

        return insights
