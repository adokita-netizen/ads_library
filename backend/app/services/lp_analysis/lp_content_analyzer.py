"""LP Content Analyzer - USP extraction, appeal axis detection, structure analysis using LLM."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class USPResult:
    """Extracted USP from LP."""

    category: str       # efficacy, ingredient, price, guarantee, authority, uniqueness, etc.
    text: str           # The USP statement
    headline: str = ""  # Associated headline
    evidence: str = ""  # Supporting evidence text
    prominence: float = 0.0  # 0-100
    position: str = ""  # above_fold, middle, bottom
    keywords: list[str] = field(default_factory=list)


@dataclass
class AppealAxisResult:
    """Appeal axis analysis result."""

    axis: str           # benefit, problem_solution, authority, social_proof, urgency, price, etc.
    strength: float     # 0-100
    evidence_texts: list[str] = field(default_factory=list)


@dataclass
class LPAnalysisResult:
    """Complete LP analysis result."""

    # Scores
    quality_score: float = 0.0
    conversion_potential: float = 0.0
    trust_score: float = 0.0
    urgency_score: float = 0.0

    # Structure
    page_flow: str = ""
    structure_summary: str = ""

    # Target persona
    target_gender: str = ""
    target_age_range: str = ""
    target_concerns: list[str] = field(default_factory=list)
    persona_summary: str = ""

    # Appeal
    primary_appeal: str = ""
    secondary_appeal: str = ""
    appeal_summary: str = ""

    # Competitive
    positioning: str = ""
    differentiation: list[str] = field(default_factory=list)

    # Copy analysis
    headline_effectiveness: float = 0.0
    cta_effectiveness: float = 0.0
    emotional_triggers: list[str] = field(default_factory=list)
    power_words: list[str] = field(default_factory=list)

    # Actionable
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    reusable_patterns: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)

    # USPs and appeals
    usps: list[USPResult] = field(default_factory=list)
    appeal_axes: list[AppealAxisResult] = field(default_factory=list)

    # Full text
    full_analysis: str = ""


class LPContentAnalyzer:
    """Analyze LP content for USPs, appeal axes, and competitive intelligence."""

    # Appeal axis keywords for heuristic analysis (fallback)
    APPEAL_KEYWORDS = {
        "benefit": [
            "効果", "実感", "結果", "変化", "改善", "ケア", "サポート",
            "パワー", "働き", "力", "理想", "叶える",
        ],
        "problem_solution": [
            "悩み", "困って", "お困り", "つらい", "コンプレックス",
            "原因", "なぜ", "理由", "そんな方", "解決",
        ],
        "authority": [
            "医師", "専門家", "監修", "博士", "研究", "特許", "認証",
            "受賞", "掲載", "メディア", "臨床試験", "エビデンス",
        ],
        "social_proof": [
            "口コミ", "レビュー", "お客様", "満足度", "リピート",
            "累計", "突破", "売上", "ランキング", "No.1",
        ],
        "urgency": [
            "限定", "期間", "残り", "今だけ", "先着", "キャンペーン",
            "終了", "急い", "お早め", "在庫", "数量限定",
        ],
        "price": [
            "円", "税込", "送料無料", "初回", "割引", "OFF",
            "お得", "コスパ", "返金保証", "定期", "特別価格",
        ],
        "comparison": [
            "比較", "違い", "他社", "従来", "一般的", "通常",
            "圧倒的", "業界初", "独自",
        ],
        "emotional": [
            "自信", "輝く", "笑顔", "幸せ", "キレイ", "美しい",
            "若々しい", "モテ", "印象", "好印象",
        ],
        "fear": [
            "放置", "悪化", "手遅れ", "老化", "危険", "リスク",
            "知らない", "まだ", "このまま",
        ],
        "novelty": [
            "新発売", "新登場", "日本初", "業界初", "特許",
            "革新", "最新", "次世代", "話題",
        ],
    }

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

    async def analyze_lp_full(
        self,
        text_content: str,
        url: str = "",
        title: str = "",
        sections_summary: str = "",
        genre: str = "",
    ) -> LPAnalysisResult:
        """Full LP analysis using LLM - USP, appeal axes, target persona, recommendations."""

        prompt = f"""以下のランディングページ（LP）の内容を詳細に分析してください。

【URL】{url}
【タイトル】{title}
【ジャンル】{genre}
【セクション構成】{sections_summary}

【本文内容】
{text_content[:8000]}

以下の観点で分析し、JSON形式で出力してください:

{{
  "quality_score": 0-100,
  "conversion_potential": 0-100,
  "trust_score": 0-100,
  "urgency_score": 0-100,

  "page_flow": "hero→problem→solution→authority→testimonial→pricing→cta のような構成フロー",
  "structure_summary": "LP構成の概要説明",

  "target_gender": "女性/男性/ユニセックス",
  "target_age_range": "30-40代 など",
  "target_concerns": ["悩み1", "悩み2"],
  "persona_summary": "ターゲットペルソナの説明",

  "primary_appeal": "benefit/problem_solution/authority/social_proof/urgency/price/comparison/emotional/fear/novelty",
  "secondary_appeal": "同上",
  "appeal_summary": "訴求戦略の説明",

  "usps": [
    {{
      "category": "efficacy/ingredient/price/guarantee/authority/uniqueness/convenience/speed/safety/experience",
      "text": "USPの内容",
      "headline": "関連する見出し",
      "evidence": "裏付けとなる記述",
      "prominence": 0-100,
      "position": "above_fold/middle/bottom",
      "keywords": ["キーワード1", "キーワード2"]
    }}
  ],

  "appeal_axes": [
    {{
      "axis": "訴求軸名",
      "strength": 0-100,
      "evidence_texts": ["根拠テキスト1", "根拠テキスト2"]
    }}
  ],

  "positioning": "競合に対するポジショニング分析",
  "differentiation": ["差別化ポイント1", "差別化ポイント2"],

  "headline_effectiveness": 0-100,
  "cta_effectiveness": 0-100,
  "emotional_triggers": ["感情トリガー1", "感情トリガー2"],
  "power_words": ["パワーワード1", "パワーワード2"],

  "strengths": ["強み1", "強み2"],
  "weaknesses": ["弱み1", "弱み2"],
  "reusable_patterns": ["自社LPに活用できるパターン1", "パターン2"],
  "improvement_suggestions": ["改善提案1", "改善提案2"],

  "full_analysis": "総合的な分析レポート（300文字程度）"
}}"""

        try:
            client = self._get_client()
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "あなたはD2C・EC広告のLPを分析するプロのマーケティングアナリストです。"
                                "USP（独自の売り）、訴求軸、ターゲット分析、競合ポジショニングを"
                                "正確に分析し、自社のLP制作に活用できるインサイトを提供してください。"
                                "特に記事LP→商品ページへの導線設計の観点で分析してください。"
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )
            )

            if not response.choices or not response.choices[0].message.content:
                raise ValueError("LLM returned empty response")
            data = json.loads(response.choices[0].message.content)
            return self._parse_llm_response(data)

        except Exception as e:
            logger.warning("llm_analysis_failed_using_heuristic", error=str(e))
            return self.analyze_lp_heuristic(text_content, title)

    def analyze_lp_heuristic(self, text_content: str, title: str = "") -> LPAnalysisResult:
        """Heuristic-based LP analysis (fallback when LLM unavailable)."""
        result = LPAnalysisResult()

        # Appeal axis scoring
        for axis, keywords in self.APPEAL_KEYWORDS.items():
            score = 0
            evidence = []
            for kw in keywords:
                count = text_content.count(kw)
                if count > 0:
                    score += min(count * 10, 30)
                    # Extract context around keyword
                    idx = text_content.find(kw)
                    if idx >= 0:
                        start = max(0, idx - 30)
                        end = min(len(text_content), idx + len(kw) + 30)
                        evidence.append(text_content[start:end].strip())

            if score > 0:
                result.appeal_axes.append(AppealAxisResult(
                    axis=axis,
                    strength=min(score, 100),
                    evidence_texts=evidence[:5],
                ))

        # Sort by strength
        result.appeal_axes.sort(key=lambda x: x.strength, reverse=True)

        if result.appeal_axes:
            result.primary_appeal = result.appeal_axes[0].axis
            if len(result.appeal_axes) > 1:
                result.secondary_appeal = result.appeal_axes[1].axis

        # Extract USPs heuristically
        result.usps = self._extract_usps_heuristic(text_content)

        # Simple scoring
        has_testimonials = any(kw in text_content for kw in ["口コミ", "お客様の声", "レビュー"])
        has_authority = any(kw in text_content for kw in ["医師", "専門家", "特許", "監修"])
        has_pricing = any(kw in text_content for kw in ["円", "価格", "初回"])
        has_guarantee = any(kw in text_content for kw in ["返金保証", "安心", "返品"])

        result.trust_score = (
            30 + (20 if has_testimonials else 0) + (25 if has_authority else 0) +
            (15 if has_guarantee else 0) + (10 if has_pricing else 0)
        )
        result.conversion_potential = min(100, sum(a.strength for a in result.appeal_axes[:3]) / 3)
        result.quality_score = (result.trust_score + result.conversion_potential) / 2
        result.urgency_score = next(
            (a.strength for a in result.appeal_axes if a.axis == "urgency"), 0
        )

        return result

    def _extract_usps_heuristic(self, text: str) -> list[USPResult]:
        """Extract USPs using keyword patterns."""
        usps = []

        usp_patterns = {
            "efficacy": [r"(\d+%?\s*(?:の方が|が)\s*実感)", r"(効果を実感[^。]*。)"],
            "ingredient": [r"((?:独自|特許|天然)\s*成分[^。]*。)", r"((?:配合|含有)[^。]*。)"],
            "price": [r"(初回[^。]*(?:円|OFF)[^。]*。)", r"(特別価格[^。]*。)"],
            "authority": [r"((?:医師|専門家)[^。]*(?:監修|推奨)[^。]*。)"],
            "uniqueness": [r"((?:日本初|業界初|独自)[^。]*。)"],
        }

        for category, patterns in usp_patterns.items():
            for pattern in patterns:
                import re
                matches = re.findall(pattern, text)
                for match_text in matches[:2]:
                    usps.append(USPResult(
                        category=category,
                        text=match_text[:300],
                        prominence=60.0,
                        position="middle",
                    ))

        return usps

    def _parse_llm_response(self, data: dict) -> LPAnalysisResult:
        """Parse LLM JSON response into LPAnalysisResult."""
        usps = []
        for usp_data in data.get("usps", []):
            usps.append(USPResult(
                category=usp_data.get("category", ""),
                text=usp_data.get("text", ""),
                headline=usp_data.get("headline", ""),
                evidence=usp_data.get("evidence", ""),
                prominence=float(usp_data.get("prominence", 0)),
                position=usp_data.get("position", ""),
                keywords=usp_data.get("keywords", []),
            ))

        appeals = []
        for appeal_data in data.get("appeal_axes", []):
            appeals.append(AppealAxisResult(
                axis=appeal_data.get("axis", ""),
                strength=float(appeal_data.get("strength", 0)),
                evidence_texts=appeal_data.get("evidence_texts", []),
            ))

        return LPAnalysisResult(
            quality_score=float(data.get("quality_score", 0)),
            conversion_potential=float(data.get("conversion_potential", 0)),
            trust_score=float(data.get("trust_score", 0)),
            urgency_score=float(data.get("urgency_score", 0)),
            page_flow=data.get("page_flow", ""),
            structure_summary=data.get("structure_summary", ""),
            target_gender=data.get("target_gender", ""),
            target_age_range=data.get("target_age_range", ""),
            target_concerns=data.get("target_concerns", []),
            persona_summary=data.get("persona_summary", ""),
            primary_appeal=data.get("primary_appeal", ""),
            secondary_appeal=data.get("secondary_appeal", ""),
            appeal_summary=data.get("appeal_summary", ""),
            positioning=data.get("positioning", ""),
            differentiation=data.get("differentiation", []),
            headline_effectiveness=float(data.get("headline_effectiveness", 0)),
            cta_effectiveness=float(data.get("cta_effectiveness", 0)),
            emotional_triggers=data.get("emotional_triggers", []),
            power_words=data.get("power_words", []),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            reusable_patterns=data.get("reusable_patterns", []),
            improvement_suggestions=data.get("improvement_suggestions", []),
            usps=usps,
            appeal_axes=appeals,
            full_analysis=data.get("full_analysis", ""),
        )
