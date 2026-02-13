"""Video ad script generation using LLMs."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ScriptSection:
    """A section of the video script."""

    section_name: str  # hook, problem, solution, benefit, cta
    duration_seconds: float
    narration: str
    visual_description: str
    text_overlay: str = ""
    audio_notes: str = ""


@dataclass
class GeneratedScript:
    """A complete generated video ad script."""

    title: str
    total_duration_seconds: float
    target_audience: str
    appeal_axis: str
    sections: list[ScriptSection] = field(default_factory=list)
    thumbnail_concept: str = ""
    hashtags: list[str] = field(default_factory=list)
    a_b_test_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "total_duration_seconds": self.total_duration_seconds,
            "target_audience": self.target_audience,
            "appeal_axis": self.appeal_axis,
            "sections": [
                {
                    "section_name": s.section_name,
                    "duration_seconds": s.duration_seconds,
                    "narration": s.narration,
                    "visual_description": s.visual_description,
                    "text_overlay": s.text_overlay,
                    "audio_notes": s.audio_notes,
                }
                for s in self.sections
            ],
            "thumbnail_concept": self.thumbnail_concept,
            "hashtags": self.hashtags,
            "a_b_test_notes": self.a_b_test_notes,
        }

    @property
    def full_narration(self) -> str:
        return "\n".join(s.narration for s in self.sections)


class ScriptGenerator:
    """Generate video ad scripts using LLMs."""

    # Standard video ad structures
    STRUCTURES = {
        "problem_solution": {
            "name": "Problem → Solution",
            "sections": ["hook", "problem", "solution", "benefit", "social_proof", "cta"],
            "description": "問題提起→解決策→ベネフィット→CTA",
        },
        "ugc_testimonial": {
            "name": "UGC Testimonial",
            "sections": ["hook", "before", "discovery", "after", "recommendation"],
            "description": "体験者目線のUGC風構成",
        },
        "product_demo": {
            "name": "Product Demo",
            "sections": ["hook", "feature_1", "feature_2", "feature_3", "offer", "cta"],
            "description": "商品特徴を順番に紹介",
        },
        "listicle": {
            "name": "Listicle (Top N)",
            "sections": ["hook", "item_1", "item_2", "item_3", "recommendation", "cta"],
            "description": "ランキング・リスト形式",
        },
        "short_impact": {
            "name": "Short Impact (15s)",
            "sections": ["hook", "key_message", "cta"],
            "description": "15秒ショートインパクト",
        },
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

    async def generate_script(
        self,
        product_name: str,
        product_description: str,
        target_audience: str,
        duration_seconds: int = 30,
        structure: str = "problem_solution",
        appeal_axis: str = "benefit",
        platform: str = "youtube",
        tone: str = "friendly",
        reference_analysis: Optional[dict] = None,
        language: str = "ja",
    ) -> GeneratedScript:
        """Generate a video ad script."""

        structure_info = self.STRUCTURES.get(structure, self.STRUCTURES["problem_solution"])

        prompt = self._build_script_prompt(
            product_name=product_name,
            product_description=product_description,
            target_audience=target_audience,
            duration_seconds=duration_seconds,
            structure_info=structure_info,
            appeal_axis=appeal_axis,
            platform=platform,
            tone=tone,
            reference_analysis=reference_analysis,
            language=language,
        )

        try:
            client = self._get_client()
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt(language),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.8,
                    max_tokens=3000,
                    response_format={"type": "json_object"},
                )
            )

            if not response.choices or not response.choices[0].message.content:
                raise ValueError("LLM returned empty response")
            content = response.choices[0].message.content
            import json
            script_data = json.loads(content)

            return self._parse_script_response(script_data, target_audience, appeal_axis)

        except Exception as e:
            logger.error("script_generation_failed", error=str(e))
            raise

    def _get_system_prompt(self, language: str) -> str:
        if language == "ja":
            return """あなたは動画広告のプロフェッショナルスクリプトライターです。
広告効果を最大化する動画台本を作成してください。

出力はJSON形式で以下の構造にしてください：
{
  "title": "台本タイトル",
  "sections": [
    {
      "section_name": "セクション名",
      "duration_seconds": 秒数,
      "narration": "ナレーション文",
      "visual_description": "映像の説明",
      "text_overlay": "テロップ文",
      "audio_notes": "BGM・SE指示"
    }
  ],
  "thumbnail_concept": "サムネイル案",
  "hashtags": ["ハッシュタグ"],
  "a_b_test_notes": "ABテスト用メモ"
}"""
        else:
            return """You are a professional video ad scriptwriter.
Create scripts that maximize ad performance.

Output in JSON format with this structure:
{
  "title": "Script title",
  "sections": [
    {
      "section_name": "section name",
      "duration_seconds": seconds,
      "narration": "narration text",
      "visual_description": "visual description",
      "text_overlay": "text overlay",
      "audio_notes": "BGM/SE notes"
    }
  ],
  "thumbnail_concept": "thumbnail concept",
  "hashtags": ["hashtags"],
  "a_b_test_notes": "A/B test notes"
}"""

    def _build_script_prompt(
        self,
        product_name: str,
        product_description: str,
        target_audience: str,
        duration_seconds: int,
        structure_info: dict,
        appeal_axis: str,
        platform: str,
        tone: str,
        reference_analysis: Optional[dict],
        language: str,
    ) -> str:
        platform_tips = {
            "youtube": "YouTube広告: 最初の5秒でスキップされないフックが重要",
            "tiktok": "TikTok広告: UGC風、縦型、テンポ重視、字幕必須",
            "instagram": "Instagram広告: ビジュアル重視、短尺、ストーリーズ対応",
            "facebook": "Facebook広告: 情報量多め、音声OFF想定でテロップ重要",
        }

        prompt = f"""以下の条件で動画広告台本を作成してください。

【商品情報】
- 商品名: {product_name}
- 商品説明: {product_description}

【ターゲット】
{target_audience}

【制作条件】
- 尺: {duration_seconds}秒
- 構成: {structure_info['name']}（{structure_info['description']}）
- セクション: {', '.join(structure_info['sections'])}
- 訴求軸: {appeal_axis}
- 媒体: {platform}
- トーン: {tone}
- {platform_tips.get(platform, '')}

【重要ポイント】
- 冒頭3秒のフック（hook）は最も重要。視聴者の注意を引く強いフレーズを使用
- CTAは明確かつ具体的に
- テロップは要点を簡潔に
- 各セクションの秒数を合計が{duration_seconds}秒になるよう配分
"""

        if reference_analysis:
            prompt += f"""
【参考分析データ】
成功事例の特徴:
- 全体感情: {reference_analysis.get('sentiment', 'N/A')}
- 使用キーワード: {reference_analysis.get('keywords', [])}
- CTA: {reference_analysis.get('cta', 'N/A')}
- フック手法: {reference_analysis.get('hook_type', 'N/A')}
上記を参考にしつつ、オリジナリティのある台本にしてください。
"""

        return prompt

    def _parse_script_response(
        self,
        data: dict,
        target_audience: str,
        appeal_axis: str,
    ) -> GeneratedScript:
        """Parse LLM response into GeneratedScript."""
        sections = []
        total_duration = 0

        for section_data in data.get("sections", []):
            duration = section_data.get("duration_seconds", 5)
            total_duration += duration
            sections.append(ScriptSection(
                section_name=section_data.get("section_name", ""),
                duration_seconds=duration,
                narration=section_data.get("narration", ""),
                visual_description=section_data.get("visual_description", ""),
                text_overlay=section_data.get("text_overlay", ""),
                audio_notes=section_data.get("audio_notes", ""),
            ))

        return GeneratedScript(
            title=data.get("title", "Untitled Script"),
            total_duration_seconds=total_duration,
            target_audience=target_audience,
            appeal_axis=appeal_axis,
            sections=sections,
            thumbnail_concept=data.get("thumbnail_concept", ""),
            hashtags=data.get("hashtags", []),
            a_b_test_notes=data.get("a_b_test_notes", ""),
        )

    async def generate_variations(
        self,
        base_script: GeneratedScript,
        num_variations: int = 3,
        variation_type: str = "hook",
    ) -> list[GeneratedScript]:
        """Generate A/B test variations of a script."""
        variations: list[GeneratedScript] = []

        variation_prompts = {
            "hook": "冒頭フック部分を変えたバリエーション",
            "cta": "CTA（行動喚起）部分を変えたバリエーション",
            "tone": "トーン・雰囲気を変えたバリエーション",
            "structure": "構成を変えたバリエーション",
        }

        prompt_instruction = variation_prompts.get(variation_type, variation_prompts["hook"])

        for i in range(num_variations):
            try:
                client = self._get_client()
                import json
                response = await asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": self._get_system_prompt("ja"),
                            },
                            {
                                "role": "user",
                                "content": f"""以下のベース台本の{prompt_instruction}を作成してください。
バリエーション {i + 1}/{num_variations}

【ベース台本】
{json.dumps(base_script.to_dict(), ensure_ascii=False, indent=2)}

{prompt_instruction}として、異なるアプローチの台本をJSON形式で出力してください。""",
                            },
                        ],
                        temperature=0.9,
                        max_tokens=3000,
                        response_format={"type": "json_object"},
                    )
                )

                if not response.choices or not response.choices[0].message.content:
                    raise ValueError("LLM returned empty response")
                content = response.choices[0].message.content
                script_data = json.loads(content)
                variation = self._parse_script_response(
                    script_data, base_script.target_audience, base_script.appeal_axis
                )
                variations.append(variation)

            except Exception as e:
                logger.error("variation_generation_failed", variation=i, error=str(e))

        return variations

    def get_available_structures(self) -> list[dict]:
        """Get list of available script structures."""
        return [
            {"key": key, **value}
            for key, value in self.STRUCTURES.items()
        ]
