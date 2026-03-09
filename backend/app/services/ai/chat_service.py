"""Core AI chat business logic."""

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ad import Ad
from app.models.ad_metrics import ProductRanking
from app.models.api_key import PlatformAPIKey
from app.models.conversation import Conversation
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.intent_classifier import IntentClassifier
from app.utils.crypto import decrypt_value


class ChatService:
    """Processes chat messages with Claude-first + rule-based fallback."""

    def __init__(self, session: Session, user_id: int | None = None):
        self.session = session
        self.user_id = user_id
        self.classifier = IntentClassifier()
        self.settings = get_settings()

    async def process_message(self, conversation_id: int | None, message: str) -> dict:
        intent = self.classifier.classify(message)
        data = self._get_intent_data(intent, message)

        provider = "rule_based"
        usage: dict[str, Any] = {}
        response_text = ""

        claude = self._get_claude_client()
        if claude:
            rag_context = self._build_rag_context(intent=intent, message=message, data=data)
            result = await claude.generate_message(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(
                    message=message,
                    intent=intent,
                    data=data,
                    rag_context=rag_context,
                ),
                user_scope=f"user:{self.user_id or 'anon'}",
            )
            if result.get("ok"):
                response_text = str(result.get("message", "")).strip()
                provider = "claude"
                usage = result.get("usage", {}) if isinstance(result.get("usage"), dict) else {}

        if not response_text:
            response_text = self._generate_response(intent, data)

        conversation = self._save_to_conversation(conversation_id, message, response_text, intent)

        return {
            "conversation_id": conversation.id,
            "response": {
                "message": response_text,
                "intent": intent,
                "provider": provider,
                "usage": usage,
                "data": data,
                "actions": self._suggest_actions(intent, data),
                "related_ad_ids": self._get_related_ad_ids(data),
            },
        }

    def _get_intent_data(self, intent: str, message: str) -> dict:
        if intent == "analyze_genre":
            return self._analyze_genre(message)
        if intent == "data_stats":
            return self._get_stats()
        if intent == "find_trends":
            return self._find_trends()
        if intent == "analyze_ad":
            return self._analyze_ad(message)
        return {}

    def _get_claude_client(self) -> ClaudeClient | None:
        if not self.settings.ai_chat_use_claude:
            return None
        api_key = self._resolve_anthropic_key()
        if not api_key:
            return None
        return ClaudeClient(
            api_key=api_key,
            model=self.settings.anthropic_model,
            max_tokens=self.settings.ai_chat_claude_max_tokens,
            timeout_seconds=self.settings.ai_chat_claude_timeout_seconds,
            requests_per_hour=self.settings.ai_chat_requests_per_hour,
            tokens_per_day=self.settings.ai_chat_tokens_per_day,
            cache_key_version=self.settings.cache_key_version,
        )

    def _resolve_anthropic_key(self) -> str | None:
        row = (
            self.session.query(PlatformAPIKey)
            .filter(
                PlatformAPIKey.platform == "anthropic",
                PlatformAPIKey.key_name == "api_key",
                PlatformAPIKey.is_active.is_(True),
            )
            .order_by(PlatformAPIKey.updated_at.desc())
            .first()
        )
        if row and row.key_value:
            try:
                return decrypt_value(row.key_value)
            except Exception:
                return row.key_value
        return self.settings.anthropic_api_key

    def _build_system_prompt(self) -> str:
        return (
            "あなたは VAAP の広告分析AIアシスタントです。"
            "返答は日本語で、数字と根拠を明示し、過度な断定を避けてください。"
            "提供されたコンテキスト外の事実は推測せず、必要なら追加質問をしてください。"
        )

    def _build_user_prompt(self, *, message: str, intent: str, data: dict, rag_context: dict) -> str:
        return (
            f"[ユーザー質問]\n{message}\n\n"
            f"[推定インテント]\n{intent}\n\n"
            f"[ルールベース抽出データ]\n{data}\n\n"
            f"[RAGコンテキスト]\n{rag_context}\n\n"
            "[出力要件]\n"
            "- まず結論\n"
            "- 次に根拠（箇条書き）\n"
            "- 最後に次アクションを2件以内で提案"
        )

    def _build_rag_context(self, *, intent: str, message: str, data: dict) -> dict:
        context: dict[str, Any] = {"intent": intent}
        context["global_stats"] = self._get_stats()

        genre = data.get("genre") if isinstance(data, dict) else None
        if not genre:
            genre = self._extract_genre(message)
        if genre:
            context["genre_snapshot"] = self._analyze_genre(genre)

        recent_ads = self.session.query(Ad).order_by(Ad.created_at.desc()).limit(5).all()
        context["recent_ads"] = [
            {
                "ad_id": ad.id,
                "title": ad.title or "(untitled)",
                "advertiser_name": ad.advertiser_name,
                "category": str(ad.category.value) if getattr(ad.category, "value", None) else None,
            }
            for ad in recent_ads
        ]
        return context

    def _extract_genre(self, message: str) -> str | None:
        text = (message or "").lower()
        mapping = {
            "beauty": ["beauty", "美容", "コスメ", "化粧品"],
            "health": ["health", "健康", "サプリ", "ダイエット"],
            "food": ["food", "食品", "フード"],
            "finance": ["finance", "金融", "投資"],
            "education": ["education", "教育", "学習"],
            "app": ["app", "アプリ"],
            "ec_d2c": ["ec", "d2c", "通販", "ec_d2c"],
            "other": ["other", "その他", "未分類"],
        }
        for genre, keywords in mapping.items():
            if any(kw in text for kw in keywords):
                return genre
        return None

    def _analyze_genre(self, message: str) -> dict:
        genre = self._extract_genre(message)
        if not genre:
            return {}

        rows = (
            self.session.query(ProductRanking)
            .filter(ProductRanking.genre == genre)
            .order_by(ProductRanking.hit_score.desc())
            .limit(50)
            .all()
        )
        if not rows:
            return {"genre": genre, "total_ads": 0, "hit_count": 0, "hit_rate": 0.0, "top_ads": []}

        total_ads = len(rows)
        hit_rows = [r for r in rows if r.is_hit]
        hit_count = len(hit_rows)
        avg_score = round(sum((r.hit_score or 0.0) for r in rows) / max(total_ads, 1), 1)
        top_rows = rows[:5]

        top_ads = []
        for r in top_rows:
            ad = self.session.query(Ad).filter(Ad.id == r.ad_id).first()
            top_ads.append(
                {
                    "ad_id": r.ad_id,
                    "title": (ad.title if ad else None) or "(untitled)",
                    "hit_score": round(float(r.hit_score or 0.0), 1),
                    "advertiser_name": r.advertiser_name,
                }
            )

        return {
            "genre": genre,
            "total_ads": total_ads,
            "hit_count": hit_count,
            "hit_rate": round((hit_count / max(total_ads, 1)) * 100.0, 1),
            "avg_hit_score": avg_score,
            "top_ads": top_ads,
            "top_ad_ids": [t["ad_id"] for t in top_ads],
        }

    def _get_stats(self) -> dict:
        total_ads = int(self.session.query(func.count(Ad.id)).scalar() or 0)
        hit_count = int(
            self.session.query(func.count(func.distinct(ProductRanking.ad_id)))
            .filter(ProductRanking.is_hit.is_(True))
            .scalar()
            or 0
        )
        avg_score = float(self.session.query(func.avg(ProductRanking.hit_score)).scalar() or 0.0)

        return {
            "total_ads": total_ads,
            "hit_count": hit_count,
            "hit_rate": round((hit_count / max(total_ads, 1)) * 100.0, 1),
            "avg_hit_score": round(avg_score, 1),
        }

    def _find_trends(self) -> dict:
        recent = self.session.query(Ad).order_by(Ad.created_at.desc()).limit(300).all()
        if not recent:
            return {"top_categories": []}

        counter: dict[str, int] = {}
        for ad in recent:
            category = str(ad.category.value) if getattr(ad.category, "value", None) else "other"
            counter[category] = counter.get(category, 0) + 1

        top_categories = [
            {"genre": genre, "count": count}
            for genre, count in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        return {"top_categories": top_categories}

    def _analyze_ad(self, message: str) -> dict:
        ids = re.findall(r"\d+", message or "")
        if not ids:
            return {}
        ad_id = int(ids[0])
        ad = self.session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return {}

        best_rank = (
            self.session.query(ProductRanking)
            .filter(ProductRanking.ad_id == ad.id)
            .order_by(ProductRanking.hit_score.desc())
            .first()
        )
        return {
            "ad_id": ad.id,
            "title": ad.title or "(untitled)",
            "advertiser_name": ad.advertiser_name,
            "category": str(ad.category.value) if getattr(ad.category, "value", None) else None,
            "hit_score": round(float((best_rank.hit_score if best_rank else 0.0) or 0.0), 1),
            "is_hit": bool(best_rank.is_hit) if best_rank else False,
        }

    def _generate_response(self, intent: str, data: dict) -> str:
        if intent == "data_stats" and data:
            return (
                f"現在DBには{data.get('total_ads', 0)}件の広告があります。"
                f"このうちHIT判定は{data.get('hit_count', 0)}件（{data.get('hit_rate', 0)}%）です。"
            )
        if intent == "analyze_genre" and data:
            if data.get("total_ads", 0) == 0:
                return f"{data.get('genre')}ジャンルのランキングデータが見つかりませんでした。"
            return (
                f"{data.get('genre')}ジャンルでは {data.get('total_ads')}件中 "
                f"{data.get('hit_count')}件がHIT（{data.get('hit_rate')}%）です。"
                "上位広告の共通要素を続けて深掘りできます。"
            )
        if intent == "find_trends" and data:
            top = data.get("top_categories", [])
            if not top:
                return "トレンド分析対象データが不足しています。"
            top_label = ", ".join(f"{x['genre']}({x['count']})" for x in top[:3])
            return f"直近の出稿傾向では {top_label} が多いです。"
        if intent == "analyze_ad" and data:
            return (
                f"広告ID {data.get('ad_id')} はスコア {data.get('hit_score')}、"
                f"HIT判定は {data.get('is_hit')} です。"
            )
        if intent == "suggest_creative":
            return "目的ジャンル・訴求・CTAを指定すると、過去HIT傾向から構成案を返せます。"
        return "もう少し具体的に質問してください。例: 「美容ジャンルのHIT広告の共通点は？」"

    def _suggest_actions(self, intent: str, data: dict) -> list[dict]:
        if intent == "analyze_genre" and data.get("genre"):
            return [
                {"label": "HIT広告一覧を見る", "view": "hit-ads", "params": {"genre": data["genre"]}},
                {"label": "トレンドを確認", "view": "trend", "params": {"genre": data["genre"]}},
            ]
        if intent == "data_stats":
            return [
                {"label": "ダッシュボードを見る", "view": "dashboard-summary", "params": {}},
                {"label": "ジャンル比較", "view": "genre-comparison", "params": {}},
            ]
        if intent == "analyze_ad" and data.get("ad_id"):
            return [{"label": "類似広告を探す", "view": "similar-ads", "params": {"ad_id": data["ad_id"]}}]
        return []

    def _get_related_ad_ids(self, data: dict) -> list[int]:
        if "top_ad_ids" in data and isinstance(data["top_ad_ids"], list):
            return [int(x) for x in data["top_ad_ids"] if str(x).isdigit()][:10]
        ad_id = data.get("ad_id")
        return [int(ad_id)] if str(ad_id).isdigit() else []

    def _save_to_conversation(
        self,
        conversation_id: int | None,
        user_message: str,
        assistant_message: str,
        intent: str,
    ) -> Conversation:
        now = datetime.now(timezone.utc).isoformat()
        conversation = None

        if conversation_id:
            query = self.session.query(Conversation).filter(Conversation.id == conversation_id)
            if self.user_id is not None:
                query = query.filter(Conversation.user_id == self.user_id)
            conversation = query.first()

        if conversation is None:
            title = (user_message or "New Conversation").strip()[:80] or "New Conversation"
            conversation = Conversation(user_id=self.user_id, title=title, messages=[])
            self.session.add(conversation)
            self.session.flush()

        messages = list(conversation.messages or [])
        messages.append({"role": "user", "content": user_message, "timestamp": now, "intent": intent})
        messages.append({"role": "assistant", "content": assistant_message, "timestamp": now, "intent": intent})
        conversation.messages = messages
        conversation.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation
