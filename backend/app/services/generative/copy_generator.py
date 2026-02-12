"""Ad copy and banner text generation using LLMs."""

import json
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class GeneratedCopy:
    """A generated ad copy."""

    headline: str
    body: str
    cta_text: str
    subheadline: str = ""
    platform: str = ""
    character_counts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "subheadline": self.subheadline,
            "body": self.body,
            "cta_text": self.cta_text,
            "platform": self.platform,
            "character_counts": {
                "headline": len(self.headline),
                "body": len(self.body),
                "cta": len(self.cta_text),
            },
        }


@dataclass
class LPCopyResult:
    """Generated landing page copy."""

    hero_headline: str
    hero_subheadline: str
    hero_cta: str
    problem_section: str
    solution_section: str
    features: list[dict] = field(default_factory=list)
    testimonials: list[dict] = field(default_factory=list)
    faq: list[dict] = field(default_factory=list)
    final_cta: str = ""

    def to_dict(self) -> dict:
        return {
            "hero": {
                "headline": self.hero_headline,
                "subheadline": self.hero_subheadline,
                "cta": self.hero_cta,
            },
            "problem_section": self.problem_section,
            "solution_section": self.solution_section,
            "features": self.features,
            "testimonials": self.testimonials,
            "faq": self.faq,
            "final_cta": self.final_cta,
        }


class CopyGenerator:
    """Generate ad copy, banner text, and LP copy using LLMs."""

    PLATFORM_SPECS = {
        "google_ads": {"headline_max": 30, "description_max": 90},
        "facebook": {"headline_max": 40, "description_max": 125},
        "instagram": {"headline_max": 40, "caption_max": 2200},
        "tiktok": {"text_max": 100},
        "youtube": {"title_max": 100, "description_max": 5000},
        "line": {"title_max": 20, "description_max": 75},
        "yahoo": {"title_max": 25, "description_max": 90},
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

    async def generate_ad_copy(
        self,
        product_name: str,
        product_description: str,
        target_audience: str,
        platform: str = "facebook",
        appeal_axis: str = "benefit",
        tone: str = "friendly",
        num_variations: int = 5,
        reference_keywords: Optional[list[str]] = None,
    ) -> list[GeneratedCopy]:
        """Generate multiple ad copy variations."""
        specs = self.PLATFORM_SPECS.get(platform, {"headline_max": 50, "description_max": 150})

        prompt = f"""以下の条件で広告コピーを{num_variations}パターン生成してください。

【商品】{product_name}
【説明】{product_description}
【ターゲット】{target_audience}
【媒体】{platform}
【訴求軸】{appeal_axis}
【トーン】{tone}
【文字数制限】{json.dumps(specs, ensure_ascii=False)}
"""
        if reference_keywords:
            prompt += f"【参考キーワード】{', '.join(reference_keywords)}\n"

        prompt += """
JSON形式で以下の構造で出力してください:
{
  "copies": [
    {
      "headline": "見出し",
      "subheadline": "サブ見出し",
      "body": "本文",
      "cta_text": "CTAボタンテキスト"
    }
  ]
}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは高いCTRを実現する広告コピーライターです。媒体特性とターゲットに最適化したコピーを作成してください。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.85,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            copies = []
            for copy_data in data.get("copies", []):
                copies.append(GeneratedCopy(
                    headline=copy_data.get("headline", ""),
                    subheadline=copy_data.get("subheadline", ""),
                    body=copy_data.get("body", ""),
                    cta_text=copy_data.get("cta_text", ""),
                    platform=platform,
                ))

            return copies

        except Exception as e:
            logger.error("copy_generation_failed", error=str(e))
            raise

    async def generate_lp_copy(
        self,
        product_name: str,
        product_description: str,
        target_audience: str,
        appeal_axis: str = "benefit",
        reference_analysis: Optional[dict] = None,
    ) -> LPCopyResult:
        """Generate landing page copy."""
        prompt = f"""以下の商品のランディングページ（LP）のコピーを作成してください。

【商品】{product_name}
【説明】{product_description}
【ターゲット】{target_audience}
【訴求軸】{appeal_axis}

JSON形式で以下の構造で出力:
{{
  "hero_headline": "ファーストビュー見出し",
  "hero_subheadline": "サブ見出し",
  "hero_cta": "メインCTA",
  "problem_section": "課題・悩みセクション",
  "solution_section": "解決策セクション",
  "features": [
    {{"title": "特徴タイトル", "description": "説明", "icon_suggestion": "アイコン提案"}}
  ],
  "testimonials": [
    {{"name": "名前", "attribute": "属性", "quote": "口コミ文"}}
  ],
  "faq": [
    {{"question": "質問", "answer": "回答"}}
  ],
  "final_cta": "最終CTA"
}}"""

        if reference_analysis:
            prompt += f"\n\n【参考：競合分析データ】\n{json.dumps(reference_analysis, ensure_ascii=False, indent=2)}"

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはコンバージョン率の高いLPコピーを作成するプロのマーケターです。心理学的アプローチを活用し、ターゲットの悩みに寄り添うコピーを作成してください。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            return LPCopyResult(
                hero_headline=data.get("hero_headline", ""),
                hero_subheadline=data.get("hero_subheadline", ""),
                hero_cta=data.get("hero_cta", ""),
                problem_section=data.get("problem_section", ""),
                solution_section=data.get("solution_section", ""),
                features=data.get("features", []),
                testimonials=data.get("testimonials", []),
                faq=data.get("faq", []),
                final_cta=data.get("final_cta", ""),
            )

        except Exception as e:
            logger.error("lp_copy_generation_failed", error=str(e))
            raise

    async def rewrite_winning_pattern(
        self,
        winning_ad_text: str,
        new_product_name: str,
        new_product_description: str,
        platform: str = "facebook",
    ) -> list[GeneratedCopy]:
        """Rewrite using a winning ad pattern (勝ちパターン模倣)."""
        prompt = f"""以下の成功した広告コピーのパターン（構成・トーン・フック手法）を分析し、
新しい商品に適用した広告コピーを3パターン作成してください。

【成功広告の原文】
{winning_ad_text}

【新しい商品】
- 商品名: {new_product_name}
- 説明: {new_product_description}
- 媒体: {platform}

パターンの本質（構成、フック、CTA手法等）を抽出し、新商品に適用してください。
単純な文言置換ではなく、パターンの本質を活かしたオリジナルコピーにしてください。

JSON形式で出力:
{{
  "pattern_analysis": "抽出したパターンの説明",
  "copies": [
    {{"headline": "見出し", "body": "本文", "cta_text": "CTA"}}
  ]
}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは広告クリエイティブの分析と制作のプロフェッショナルです。成功パターンの本質を理解し、新しい商品に応用する能力に長けています。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.85,
                max_tokens=2500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            copies = []
            for copy_data in data.get("copies", []):
                copies.append(GeneratedCopy(
                    headline=copy_data.get("headline", ""),
                    body=copy_data.get("body", ""),
                    cta_text=copy_data.get("cta_text", ""),
                    platform=platform,
                ))

            return copies

        except Exception as e:
            logger.error("winning_pattern_rewrite_failed", error=str(e))
            raise
