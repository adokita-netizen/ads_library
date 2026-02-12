"""LP Comparator - compare own LP against competitor LPs."""

import json
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class AxisComparison:
    axis: str
    own_strength: float
    competitor_avg: float
    gap: float  # positive = own is stronger


@dataclass
class LPCompareResult:
    """Full comparison result."""
    # Scores
    own_quality: float = 0.0
    competitor_avg_quality: float = 0.0
    own_conversion: float = 0.0
    competitor_avg_conversion: float = 0.0
    own_trust: float = 0.0
    competitor_avg_trust: float = 0.0

    # Appeal comparison
    appeal_comparison: list[AxisComparison] = field(default_factory=list)

    # USP gaps
    missing_usp_categories: list[str] = field(default_factory=list)

    # Structure
    own_flow: str = ""
    common_competitor_flows: list[str] = field(default_factory=list)

    # Recommendations
    strengths_vs_competitors: list[str] = field(default_factory=list)
    improvement_opportunities: list[str] = field(default_factory=list)
    quick_wins: list[str] = field(default_factory=list)


class LPComparator:
    """Compare own LP performance against competitors."""

    def __init__(self, llm_client=None, model: str = "gpt-4-turbo-preview"):
        self._llm_client = llm_client
        self.model = model

    def _get_client(self):
        if self._llm_client is None:
            try:
                import openai
                self._llm_client = openai.OpenAI()
            except Exception as e:
                logger.error("openai_client_init_failed", error=str(e))
                raise
        return self._llm_client

    def compare_scores(
        self,
        own_analysis: dict,
        competitor_analyses: list[dict],
    ) -> LPCompareResult:
        """Compare scores between own LP and competitors."""
        result = LPCompareResult()

        # Own scores
        result.own_quality = own_analysis.get("quality_score", 0) or 0
        result.own_conversion = own_analysis.get("conversion_potential", 0) or 0
        result.own_trust = own_analysis.get("trust_score", 0) or 0
        result.own_flow = own_analysis.get("page_flow", "")

        # Competitor averages
        if competitor_analyses:
            n = len(competitor_analyses)
            result.competitor_avg_quality = sum(
                (c.get("quality_score", 0) or 0) for c in competitor_analyses
            ) / n
            result.competitor_avg_conversion = sum(
                (c.get("conversion_potential", 0) or 0) for c in competitor_analyses
            ) / n
            result.competitor_avg_trust = sum(
                (c.get("trust_score", 0) or 0) for c in competitor_analyses
            ) / n

        # Appeal axis comparison
        own_appeals = {
            a.get("axis", ""): a.get("strength", 0)
            for a in own_analysis.get("appeal_axes", [])
        }

        # Aggregate competitor appeals
        comp_appeal_totals: dict[str, list[float]] = {}
        for ca in competitor_analyses:
            for appeal in ca.get("appeal_axes", []):
                axis = appeal.get("axis", "")
                if axis:
                    if axis not in comp_appeal_totals:
                        comp_appeal_totals[axis] = []
                    comp_appeal_totals[axis].append(appeal.get("strength", 0))

        # Build comparison for all known axes
        all_axes = set(own_appeals.keys()) | set(comp_appeal_totals.keys())
        for axis in all_axes:
            own_str = own_appeals.get(axis, 0)
            comp_vals = comp_appeal_totals.get(axis, [])
            comp_avg = sum(comp_vals) / len(comp_vals) if comp_vals else 0
            result.appeal_comparison.append(AxisComparison(
                axis=axis,
                own_strength=own_str,
                competitor_avg=round(comp_avg, 1),
                gap=round(own_str - comp_avg, 1),
            ))

        # Sort by gap (worst first - areas to improve)
        result.appeal_comparison.sort(key=lambda x: x.gap)

        # USP gap analysis
        own_usp_cats = set(
            u.get("category", "") for u in own_analysis.get("usps", [])
        )
        comp_usp_cats: set[str] = set()
        for ca in competitor_analyses:
            for u in ca.get("usps", []):
                comp_usp_cats.add(u.get("category", ""))
        result.missing_usp_categories = list(comp_usp_cats - own_usp_cats)

        # Competitor flows
        flows = [ca.get("page_flow", "") for ca in competitor_analyses if ca.get("page_flow")]
        result.common_competitor_flows = list(set(flows))[:5]

        return result

    async def generate_comparison_insights(
        self,
        own_analysis: dict,
        competitor_analyses: list[dict],
        product_name: str = "",
        genre: str = "",
    ) -> LPCompareResult:
        """Generate detailed comparison insights using LLM."""
        # First get numeric comparison
        result = self.compare_scores(own_analysis, competitor_analyses)

        # Build prompt for LLM recommendations
        comparison_summary = {
            "own_scores": {
                "quality": result.own_quality,
                "conversion": result.own_conversion,
                "trust": result.own_trust,
            },
            "competitor_avg_scores": {
                "quality": result.competitor_avg_quality,
                "conversion": result.competitor_avg_conversion,
                "trust": result.competitor_avg_trust,
            },
            "appeal_gaps": [
                {"axis": ac.axis, "own": ac.own_strength, "comp_avg": ac.competitor_avg, "gap": ac.gap}
                for ac in result.appeal_comparison[:8]
            ],
            "missing_usps": result.missing_usp_categories,
            "own_flow": result.own_flow,
            "competitor_flows": result.common_competitor_flows[:3],
        }

        prompt = f"""以下の自社LP vs 競合LP比較データを分析し、改善提案を作成してください。

【商品】{product_name}
【ジャンル】{genre}
【比較データ】
{json.dumps(comparison_summary, ensure_ascii=False, indent=2)}

JSON形式で出力:
{{
  "strengths_vs_competitors": ["競合に対する強み1", "強み2", "強み3"],
  "improvement_opportunities": ["改善機会1", "改善機会2", "改善機会3"],
  "quick_wins": ["すぐに実施できる改善1", "改善2", "改善3"]
}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたはLP最適化の専門コンサルタントです。"
                            "自社LPと競合LPの比較データを分析し、"
                            "具体的で実行可能な改善提案を行ってください。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            data = json.loads(response.choices[0].message.content)
            result.strengths_vs_competitors = data.get("strengths_vs_competitors", [])
            result.improvement_opportunities = data.get("improvement_opportunities", [])
            result.quick_wins = data.get("quick_wins", [])

        except Exception as e:
            logger.warning("comparison_llm_failed_using_heuristic", error=str(e))
            result.strengths_vs_competitors = [
                ac.axis + "の訴求が競合より強い"
                for ac in result.appeal_comparison if ac.gap > 10
            ][:3] or ["分析データが不足しています"]
            result.improvement_opportunities = [
                ac.axis + "の訴求を強化する余地がある"
                for ac in result.appeal_comparison if ac.gap < -10
            ][:3] or ["競合との差が小さく、現状を維持"]
            result.quick_wins = []
            if result.missing_usp_categories:
                result.quick_wins.append(
                    f"競合が使用している{result.missing_usp_categories[0]}のUSPを追加"
                )

        return result
