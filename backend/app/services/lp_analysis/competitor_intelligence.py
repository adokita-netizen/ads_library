"""Competitor LP Intelligence - analyze regional/target patterns across competitors."""

import json
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class CompetitorAppealPattern:
    """Aggregated appeal pattern across competitor LPs."""

    appeal_axis: str
    avg_strength: float
    usage_count: int
    top_keywords: list[str] = field(default_factory=list)
    sample_texts: list[str] = field(default_factory=list)


@dataclass
class GenreInsight:
    """Insights for a specific genre/market segment."""

    genre: str
    total_lps_analyzed: int
    dominant_appeal: str
    appeal_distribution: list[CompetitorAppealPattern] = field(default_factory=list)
    common_usps: list[dict] = field(default_factory=list)
    avg_quality_score: float = 0.0
    common_structures: list[str] = field(default_factory=list)
    target_personas: list[dict] = field(default_factory=list)
    pricing_patterns: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class USPFlowRecommendation:
    """Recommended USP → 記事LP flow based on competitor analysis."""

    recommended_primary_usp: str
    recommended_appeal_axis: str
    article_lp_structure: list[dict] = field(default_factory=list)
    headline_suggestions: list[str] = field(default_factory=list)
    differentiation_opportunities: list[str] = field(default_factory=list)
    competitor_gaps: list[str] = field(default_factory=list)
    estimated_effectiveness: float = 0.0
    reasoning: str = ""


class CompetitorIntelligence:
    """Analyze competitor LP patterns and generate strategic insights."""

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

    def aggregate_appeal_patterns(
        self, lp_analyses: list[dict]
    ) -> list[CompetitorAppealPattern]:
        """Aggregate appeal axis data across multiple LPs."""
        axis_data: dict[str, dict] = {}

        for analysis in lp_analyses:
            for appeal in analysis.get("appeal_axes", []):
                axis = appeal.get("axis", "")
                if not axis:
                    continue

                if axis not in axis_data:
                    axis_data[axis] = {
                        "strengths": [],
                        "count": 0,
                        "keywords": [],
                        "samples": [],
                    }

                axis_data[axis]["strengths"].append(float(appeal.get("strength", 0)))
                axis_data[axis]["count"] += 1
                axis_data[axis]["samples"].extend(appeal.get("evidence_texts", [])[:2])

        patterns = []
        for axis, data in axis_data.items():
            avg = sum(data["strengths"]) / len(data["strengths"]) if data["strengths"] else 0
            patterns.append(CompetitorAppealPattern(
                appeal_axis=axis,
                avg_strength=round(avg, 1),
                usage_count=data["count"],
                sample_texts=data["samples"][:5],
            ))

        patterns.sort(key=lambda x: x.avg_strength, reverse=True)
        return patterns

    def aggregate_usp_patterns(self, lp_analyses: list[dict]) -> list[dict]:
        """Aggregate USP patterns across competitor LPs."""
        category_data: dict[str, list[dict]] = {}

        for analysis in lp_analyses:
            for usp in analysis.get("usps", []):
                cat = usp.get("category", "other")
                if cat not in category_data:
                    category_data[cat] = []
                category_data[cat].append({
                    "text": usp.get("text", ""),
                    "prominence": usp.get("prominence", 0),
                    "keywords": usp.get("keywords", []),
                })

        results = []
        for category, items in category_data.items():
            avg_prominence = sum(i["prominence"] for i in items) / len(items) if items else 0
            all_keywords = []
            for item in items:
                all_keywords.extend(item.get("keywords", []))

            # Count keyword frequency
            kw_freq: dict[str, int] = {}
            for kw in all_keywords:
                kw_freq[kw] = kw_freq.get(kw, 0) + 1
            top_kw = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:10]

            results.append({
                "category": category,
                "count": len(items),
                "avg_prominence": round(avg_prominence, 1),
                "top_keywords": [kw for kw, _ in top_kw],
                "sample_texts": [i["text"] for i in items[:3]],
            })

        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    async def generate_genre_insight(
        self,
        genre: str,
        lp_analyses: list[dict],
    ) -> GenreInsight:
        """Generate insights for a genre based on multiple LP analyses."""
        appeal_patterns = self.aggregate_appeal_patterns(lp_analyses)
        usp_patterns = self.aggregate_usp_patterns(lp_analyses)

        insight = GenreInsight(
            genre=genre,
            total_lps_analyzed=len(lp_analyses),
            dominant_appeal=appeal_patterns[0].appeal_axis if appeal_patterns else "",
            appeal_distribution=appeal_patterns,
            common_usps=usp_patterns,
            avg_quality_score=sum(
                a.get("quality_score", 0) for a in lp_analyses
            ) / max(len(lp_analyses), 1),
        )

        # Extract common structures
        structures = [a.get("page_flow", "") for a in lp_analyses if a.get("page_flow")]
        insight.common_structures = list(set(structures))[:5]

        # Extract target personas
        personas = []
        for a in lp_analyses:
            if a.get("target_gender") or a.get("target_age_range"):
                personas.append({
                    "gender": a.get("target_gender", ""),
                    "age_range": a.get("target_age_range", ""),
                    "concerns": a.get("target_concerns", []),
                })
        insight.target_personas = personas[:10]

        return insight

    async def generate_usp_flow_recommendation(
        self,
        product_name: str,
        product_description: str,
        target_audience: str,
        genre: str,
        competitor_analyses: list[dict],
    ) -> USPFlowRecommendation:
        """Generate USP → 記事LP flow recommendation based on competitor intelligence."""

        appeal_patterns = self.aggregate_appeal_patterns(competitor_analyses)
        usp_patterns = self.aggregate_usp_patterns(competitor_analyses)

        # Summarize competitor data for LLM
        competitor_summary = {
            "appeal_patterns": [
                {"axis": p.appeal_axis, "strength": p.avg_strength, "usage": p.usage_count}
                for p in appeal_patterns[:8]
            ],
            "usp_patterns": usp_patterns[:6],
            "common_structures": list(set(
                a.get("page_flow", "") for a in competitor_analyses if a.get("page_flow")
            ))[:5],
            "competitor_count": len(competitor_analyses),
        }

        prompt = f"""以下の競合分析データを基に、新商品の「USP → 記事LP」の導線設計を提案してください。

【新商品情報】
- 商品名: {product_name}
- 説明: {product_description}
- ターゲット: {target_audience}
- ジャンル: {genre}

【競合LP分析サマリー】
{json.dumps(competitor_summary, ensure_ascii=False, indent=2)}

以下の観点で戦略を提案してください:

1. 競合が多用している訴求軸を踏まえた差別化ポイント
2. 記事LPの推奨セクション構成（USPからCTAへの流れ）
3. 見出し案（3パターン）
4. 競合の弱点・カバーされていない訴求

JSON形式で出力:
{{
  "recommended_primary_usp": "推奨するメインUSP",
  "recommended_appeal_axis": "推奨する訴求軸",
  "article_lp_structure": [
    {{
      "section": "セクション名",
      "purpose": "目的",
      "content_guide": "内容ガイド",
      "appeal_technique": "使用する訴求テクニック"
    }}
  ],
  "headline_suggestions": ["見出し案1", "見出し案2", "見出し案3"],
  "differentiation_opportunities": ["差別化ポイント1", "差別化ポイント2"],
  "competitor_gaps": ["競合がカバーしていない訴求1", "訴求2"],
  "estimated_effectiveness": 0-100,
  "reasoning": "推奨理由の説明"
}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたはD2C/EC広告のLP戦略コンサルタントです。"
                            "競合分析データを基に、USP設計から記事LP構成までの導線を設計します。"
                            "データドリブンな提案を心がけ、競合との差別化を重視してください。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )

            data = json.loads(response.choices[0].message.content)
            return self._parse_flow_recommendation(data)

        except Exception as e:
            logger.warning("flow_recommendation_llm_failed", error=str(e))
            return self._generate_heuristic_recommendation(
                appeal_patterns, usp_patterns, product_name
            )

    def _parse_flow_recommendation(self, data: dict) -> USPFlowRecommendation:
        return USPFlowRecommendation(
            recommended_primary_usp=data.get("recommended_primary_usp", ""),
            recommended_appeal_axis=data.get("recommended_appeal_axis", ""),
            article_lp_structure=data.get("article_lp_structure", []),
            headline_suggestions=data.get("headline_suggestions", []),
            differentiation_opportunities=data.get("differentiation_opportunities", []),
            competitor_gaps=data.get("competitor_gaps", []),
            estimated_effectiveness=float(data.get("estimated_effectiveness", 0)),
            reasoning=data.get("reasoning", ""),
        )

    def _generate_heuristic_recommendation(
        self,
        appeal_patterns: list[CompetitorAppealPattern],
        usp_patterns: list[dict],
        product_name: str,
    ) -> USPFlowRecommendation:
        """Fallback: generate recommendation from heuristic patterns."""
        # Find least-used high-value appeal for differentiation
        top_appeal = appeal_patterns[0].appeal_axis if appeal_patterns else "benefit"

        # Standard article LP structure
        structure = [
            {"section": "フック/問題提起", "purpose": "読者の注意を引き悩みに共感", "content_guide": "ターゲットの悩みを具体的に描写", "appeal_technique": "問題共感型フック"},
            {"section": "原因の深掘り", "purpose": "なぜ解決できないのかを説明", "content_guide": "一般的な解決法の問題点を指摘", "appeal_technique": "教育・啓蒙"},
            {"section": "解決策の提示", "purpose": "商品を解決策として紹介", "content_guide": f"{product_name}の独自アプローチ", "appeal_technique": "USP訴求"},
            {"section": "権威性/エビデンス", "purpose": "信頼性を構築", "content_guide": "専門家監修、研究データ、特許情報", "appeal_technique": "権威性訴求"},
            {"section": "口コミ/体験談", "purpose": "社会的証明", "content_guide": "年代・悩み別のリアルな体験談", "appeal_technique": "社会的証明"},
            {"section": "比較優位性", "purpose": "競合との差別化", "content_guide": "成分量、価格、独自性の比較", "appeal_technique": "比較訴求"},
            {"section": "オファー/CTA", "purpose": "購入促進", "content_guide": "初回特別価格、返金保証、限定特典", "appeal_technique": "緊急性+価格訴求"},
        ]

        return USPFlowRecommendation(
            recommended_primary_usp=f"{product_name}の独自の価値提案",
            recommended_appeal_axis=top_appeal,
            article_lp_structure=structure,
            headline_suggestions=[
                f"【衝撃】{product_name}が選ばれる3つの理由",
                f"まだ知らないの？{product_name}で変わる新習慣",
                f"専門家も注目！{product_name}の実力とは",
            ],
            differentiation_opportunities=["競合がカバーしていない訴求軸を攻める", "独自成分/技術を前面に"],
            competitor_gaps=["エビデンス不足の競合が多い", "長期使用のベネフィット訴求が少ない"],
            estimated_effectiveness=65.0,
            reasoning="競合分析に基づくヒューリスティック推奨。LLM分析が利用可能になるとより精度の高い推奨が生成されます。",
        )
