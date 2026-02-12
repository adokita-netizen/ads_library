"""Unified creative generation engine."""

import json
from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.services.generative.copy_generator import CopyGenerator
from app.services.generative.script_generator import ScriptGenerator

logger = structlog.get_logger()


@dataclass
class StoryboardFrame:
    """A single frame in a storyboard."""

    frame_number: int
    timestamp_range: str
    visual_description: str
    text_overlay: str
    narration: str
    camera_direction: str = ""
    transition: str = ""


@dataclass
class Storyboard:
    """Generated storyboard for a video ad."""

    title: str
    duration_seconds: int
    frames: list[StoryboardFrame] = field(default_factory=list)
    style_notes: str = ""
    music_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "frames": [
                {
                    "frame_number": f.frame_number,
                    "timestamp_range": f.timestamp_range,
                    "visual_description": f.visual_description,
                    "text_overlay": f.text_overlay,
                    "narration": f.narration,
                    "camera_direction": f.camera_direction,
                    "transition": f.transition,
                }
                for f in self.frames
            ],
            "style_notes": self.style_notes,
            "music_notes": self.music_notes,
        }


@dataclass
class ImprovementSuggestion:
    """Improvement suggestion for an existing ad."""

    category: str  # hook, cta, pacing, visual, copy, targeting
    current_state: str
    suggestion: str
    priority: str  # high, medium, low
    expected_impact: str


class CreativeEngine:
    """Unified creative generation engine combining all generative capabilities."""

    def __init__(
        self,
        script_generator: Optional[ScriptGenerator] = None,
        copy_generator: Optional[CopyGenerator] = None,
        llm_client=None,
        model: str = "gpt-4-turbo-preview",
    ):
        self.script_generator = script_generator or ScriptGenerator(llm_client=llm_client, model=model)
        self.copy_generator = copy_generator or CopyGenerator(llm_client=llm_client, model=model)
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

    async def generate_storyboard(
        self,
        product_name: str,
        product_description: str,
        target_audience: str,
        duration_seconds: int = 15,
        platform: str = "tiktok",
        style: str = "ugc",
    ) -> Storyboard:
        """Generate a visual storyboard for short video ads."""
        prompt = f"""以下の条件でショート動画広告のストーリーボードを作成してください。

【商品】{product_name}
【説明】{product_description}
【ターゲット】{target_audience}
【尺】{duration_seconds}秒
【媒体】{platform}
【スタイル】{style}

各フレーム（2-3秒単位）の映像内容、テロップ、ナレーション、カメラワーク、トランジションを具体的に指定してください。

JSON形式で出力:
{{
  "title": "ストーリーボードタイトル",
  "frames": [
    {{
      "frame_number": 1,
      "timestamp_range": "0:00-0:03",
      "visual_description": "映像の詳細説明",
      "text_overlay": "テロップ文",
      "narration": "ナレーション",
      "camera_direction": "カメラワーク指示",
      "transition": "トランジション種類"
    }}
  ],
  "style_notes": "全体のスタイル指示",
  "music_notes": "BGM・音楽指示"
}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはショート動画広告制作のプロディレクターです。バズる動画の構成を熟知し、視聴者を最後まで惹きつけるストーリーボードを作成します。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=2500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            frames = [
                StoryboardFrame(
                    frame_number=f.get("frame_number", i + 1),
                    timestamp_range=f.get("timestamp_range", ""),
                    visual_description=f.get("visual_description", ""),
                    text_overlay=f.get("text_overlay", ""),
                    narration=f.get("narration", ""),
                    camera_direction=f.get("camera_direction", ""),
                    transition=f.get("transition", ""),
                )
                for i, f in enumerate(data.get("frames", []))
            ]

            return Storyboard(
                title=data.get("title", "Untitled"),
                duration_seconds=duration_seconds,
                frames=frames,
                style_notes=data.get("style_notes", ""),
                music_notes=data.get("music_notes", ""),
            )

        except Exception as e:
            logger.error("storyboard_generation_failed", error=str(e))
            raise

    async def suggest_improvements(
        self,
        ad_analysis: dict,
        current_metrics: Optional[dict] = None,
    ) -> list[ImprovementSuggestion]:
        """Generate improvement suggestions based on ad analysis."""
        prompt = f"""以下の広告分析データを基に、クリエイティブ改善提案を行ってください。

【広告分析データ】
{json.dumps(ad_analysis, ensure_ascii=False, indent=2)}
"""
        if current_metrics:
            prompt += f"""
【現在のパフォーマンス】
{json.dumps(current_metrics, ensure_ascii=False, indent=2)}
"""

        prompt += """
以下の観点から改善提案をJSON形式で出力してください:
{
  "suggestions": [
    {
      "category": "改善カテゴリ (hook/cta/pacing/visual/copy/targeting)",
      "current_state": "現状の問題点",
      "suggestion": "具体的な改善提案",
      "priority": "優先度 (high/medium/low)",
      "expected_impact": "期待される効果"
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
                        "content": "あなたは広告パフォーマンス改善の専門家です。データに基づいた具体的で実行可能な改善提案を行います。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            suggestions = [
                ImprovementSuggestion(
                    category=s.get("category", ""),
                    current_state=s.get("current_state", ""),
                    suggestion=s.get("suggestion", ""),
                    priority=s.get("priority", "medium"),
                    expected_impact=s.get("expected_impact", ""),
                )
                for s in data.get("suggestions", [])
            ]

            return suggestions

        except Exception as e:
            logger.error("improvement_suggestion_failed", error=str(e))
            raise

    async def generate_ab_test_plan(
        self,
        base_creative: dict,
        test_variables: list[str] | None = None,
        num_variations: int = 3,
    ) -> dict:
        """Generate an A/B test plan with variations."""
        if not test_variables:
            test_variables = ["hook", "cta", "visual_style"]

        prompt = f"""以下のベースクリエイティブに対するA/Bテスト計画を作成してください。

【ベースクリエイティブ】
{json.dumps(base_creative, ensure_ascii=False, indent=2)}

【テスト変数】{', '.join(test_variables)}
【バリエーション数】{num_variations}

各バリエーションの変更点、仮説、期待される結果を含めてください。

JSON形式で出力:
{{
  "test_name": "テスト名",
  "hypothesis": "テスト仮説",
  "test_variables": ["テスト変数"],
  "variations": [
    {{
      "variation_id": "A",
      "name": "バリエーション名",
      "changes": "変更内容",
      "hypothesis": "この変更の仮説",
      "creative_details": {{}}
    }}
  ],
  "success_metrics": ["主要KPI"],
  "recommended_duration_days": 7,
  "traffic_split": "均等分割推奨"
}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは広告A/Bテストの設計専門家です。統計的に有意な結果が得られるテスト計画を設計します。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2500,
                response_format={"type": "json_object"},
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error("ab_test_plan_failed", error=str(e))
            raise
