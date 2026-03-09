"""Rule-based intent classification for AI chat."""


class IntentClassifier:
    """Simple keyword matcher for chat intent routing."""

    INTENTS = {
        "analyze_ad": [
            "この広告",
            "広告を分析",
            "ad ",
            "ad#",
            "ad_id",
            "なぜhit",
            "why hit",
        ],
        "analyze_genre": [
            "ジャンル",
            "美容",
            "健康",
            "ダイエット",
            "共通点",
            "パターン",
            "genre",
        ],
        "compare_ads": [
            "比較",
            "違い",
            "どっち",
            "vs",
            "compare",
        ],
        "find_trends": [
            "トレンド",
            "急上昇",
            "最近",
            "伸びている",
            "trend",
            "rising",
        ],
        "suggest_creative": [
            "提案",
            "アイデア",
            "どんな広告",
            "作りたい",
            "recommend",
            "suggest",
        ],
        "data_stats": [
            "何件",
            "いくつ",
            "合計",
            "平均",
            "統計",
            "stats",
            "count",
        ],
    }

    def classify(self, message: str) -> str:
        message_lower = (message or "").lower()
        scores: dict[str, int] = {}

        for intent, keywords in self.INTENTS.items():
            scores[intent] = sum(1 for kw in keywords if kw in message_lower)

        if not scores:
            return "general"

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

