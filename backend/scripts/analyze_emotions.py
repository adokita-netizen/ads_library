#!/usr/bin/env python3
"""Emotion analysis for ad titles and descriptions.

Analyzes ad text for emotional triggers using keyword matching.
Categories: anxiety, hope, urgency, curiosity, trust, fear
Scores each ad 0-100 for dominant emotion.
Stores in ad_metadata.emotion_analysis = {"dominant": "anxiety", "scores": {...}}

No external AI needed - pure keyword matching.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_emotions.py
"""

import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Emotion keyword dictionaries (Japanese + English)
# Each keyword has a weight (1-3) indicating how strongly it signals the emotion
# ---------------------------------------------------------------------------

EMOTION_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "anxiety": [
        # Japanese - spec required
        ("\u60a9\u307f", 3),          # 悩み
        ("\u4e0d\u5b89", 3),          # 不安
        ("\u5fc3\u914d", 3),          # 心配
        ("\u8001\u5316", 2),          # 老化
        ("\u5931\u6557", 2),          # 失敗
        ("\u5371\u967a", 2),          # 危険
        ("\u30c8\u30e9\u30d6\u30eb", 2),  # トラブル
        ("\u30ea\u30b9\u30af", 2),    # リスク
        ("\u5f8c\u6094", 3),          # 後悔
        ("\u7126\u308a", 2),          # 焦り
        # Additional Japanese
        ("\u60a9\u3093\u3067", 2),    # 悩んで
        ("\u6c17\u306b\u306a\u308b", 2),  # 気になる
        ("\u30b9\u30c8\u30ec\u30b9", 2),  # ストレス
        ("\u30b3\u30f3\u30d7\u30ec\u30c3\u30af\u30b9", 2),  # コンプレックス
        ("\u3053\u306e\u307e\u307e", 2),  # このまま
        ("\u653e\u7f6e", 2),          # 放置
        ("\u5927\u4e08\u592b", 1),    # 大丈夫
        ("\u3084\u3070\u3044", 2),    # やばい
        ("\u8b66\u544a", 2),          # 警告
        ("\u6ce8\u610f", 1),          # 注意
        # English
        ("worry", 2), ("concern", 2), ("anxiety", 3), ("stressed", 2),
        ("problem", 1), ("trouble", 1), ("suffering", 2),
    ],
    "hope": [
        # Japanese - spec required
        ("\u7406\u60f3", 3),          # 理想
        ("\u5922", 2),                # 夢
        ("\u672a\u6765", 2),          # 未来
        ("\u53ef\u80fd\u6027", 2),    # 可能性
        ("\u30c1\u30e3\u30f3\u30b9", 2),  # チャンス
        ("\u5e78\u305b", 2),          # 幸せ
        ("\u7f8e\u3057\u3044", 2),    # 美しい
        ("\u82e5\u3044", 2),          # 若い
        ("\u52b9\u679c", 1),          # 効果
        ("\u5b9f\u73fe", 2),          # 実現
        # Additional Japanese
        ("\u5e0c\u671b", 3),          # 希望
        ("\u53f6\u3048", 2),          # 叶え
        ("\u5909\u308f\u308b", 2),    # 変わる
        ("\u5909\u308f\u308c\u308b", 2),  # 変われる
        ("\u751f\u307e\u308c\u5909\u308f", 2),  # 生まれ変わ
        ("\u7f8e\u3057", 2),          # 美し
        ("\u30ad\u30ec\u30a4", 2),    # キレイ
        ("\u8f1d", 2),                # 輝
        ("\u7b11\u9854", 2),          # 笑顔
        ("\u6539\u5584", 2),          # 改善
        ("\u6210\u529f", 2),          # 成功
        ("\u5b9f\u611f", 2),          # 実感
        ("\u5b89\u5fc3", 2),          # 安心
        # English
        ("hope", 3), ("dream", 2), ("beautiful", 2), ("transform", 2),
        ("amazing", 2), ("wonderful", 2), ("better", 1), ("improve", 1),
    ],
    "urgency": [
        # Japanese - spec required
        ("\u4eca\u3059\u3050", 2),    # 今すぐ
        ("\u9650\u5b9a", 3),          # 限定
        ("\u6b8b\u308a", 2),          # 残り
        ("\u6025\u3052", 2),          # 急げ
        ("\u672c\u65e5", 2),          # 本日
        ("\u7de0\u5207", 3),          # 締切
        ("\u65e9\u3044", 1),          # 早い
        ("\u30e9\u30b9\u30c8", 2),    # ラスト
        ("\u7d42\u4e86", 2),          # 終了
        ("\u671f\u9593\u9650\u5b9a", 3),  # 期間限定
        # Additional Japanese
        ("\u4eca\u3060\u3051", 3),    # 今だけ
        ("\u672c\u65e5\u9650\u308a", 3),  # 本日限り
        ("\u6025\u3044\u3067", 2),    # 急いで
        ("\u304a\u6025\u304e", 2),    # お急ぎ
        ("\u5148\u7740", 2),          # 先着
        ("\u6570\u91cf\u9650\u5b9a", 3),  # 数量限定
        ("\u5728\u5eab\u50c5\u304b", 2),  # 在庫僅か
        ("\u7d42\u4e86\u9593\u8fd1", 2),  # 終了間近
        ("\u6700\u5f8c", 2),          # 最後
        ("\u3042\u3068\u308f\u305a\u304b", 2),  # あとわずか
        ("\u5373\u65e5", 1),          # 即日
        ("\u898b\u9003\u3059\u306a", 2),  # 見逃すな
        # English
        ("limited", 3), ("hurry", 2), ("now", 1), ("last chance", 3),
        ("ending soon", 3), ("deadline", 3), ("final", 2), ("urgent", 3),
    ],
    "curiosity": [
        # Japanese - spec required
        ("\u79d8\u5bc6", 3),          # 秘密
        ("\u65b9\u6cd5", 1),          # 方法
        ("\u7406\u7531", 1),          # 理由
        ("\u5b9f\u306f", 3),          # 実は
        ("\u9a5a\u304d", 2),          # 驚き
        ("\u610f\u5916", 2),          # 意外
        ("\u771f\u5b9f", 2),          # 真実
        ("\u77e5\u3089\u306a\u3044", 2),  # 知らない
        ("\u306a\u305c", 2),          # なぜ
        ("\u88cf\u30ef\u30b6", 3),    # 裏ワザ (spec: 裏技)
        # Additional Japanese
        ("\u88cf\u6280", 3),          # 裏技
        ("\u77e5\u3063\u3066\u3044", 2),  # 知ってい
        ("\u3054\u5b58\u77e5", 2),    # ご存知
        ("\u307e\u3060", 1),          # まだ
        ("\u8862\u6483", 3),          # 衝撃
        ("\u65b0\u5e38\u8b58", 2),    # 新常識
        ("\u672c\u5f53", 1),          # 本当
        ("\u539f\u56e0", 1),          # 原因
        ("\u8a71\u984c", 2),          # 話題
        ("\u6ce8\u76ee", 2),          # 注目
        # English
        ("secret", 3), ("discover", 2), ("surprising", 2), ("hidden", 2),
        ("why", 1), ("how", 1), ("truth", 2), ("revealed", 3),
    ],
    "trust": [
        # Japanese - spec required
        ("\u5b9f\u7e3e", 3),          # 実績
        ("\u6e80\u8db3\u5ea6", 3),    # 満足度
        ("\u53e3\u30b3\u30df", 2),    # 口コミ
        ("\u533b\u5e2b", 2),          # 医師
        ("\u5c02\u9580", 2),          # 専門
        ("\u8a8d\u5b9a", 2),          # 認定
        ("\u7b2c1\u4f4d", 3),         # 第1位
        ("No.1", 3),
        ("\u53d7\u8cde", 2),          # 受賞
        ("\u7279\u8a31", 2),          # 特許
        # Additional Japanese
        ("\u5b89\u5fc3", 2),          # 安心
        ("\u5b89\u5168", 2),          # 安全
        ("\u4fe1\u983c", 3),          # 信頼
        ("\u30e9\u30f3\u30ad\u30f3\u30b0", 2),  # ランキング
        ("\u7d2f\u8a08", 2),          # 累計
        ("\u4e07\u4eba", 2),          # 万人
        ("\u76e3\u4fee", 2),          # 監修
        ("\u4fdd\u8a3c", 2),          # 保証
        ("\u8fd4\u91d1", 2),          # 返金
        ("\u30ea\u30d4\u30fc\u30c8", 2),  # リピート
        # English
        ("trust", 3), ("proven", 2), ("certified", 2), ("guaranteed", 2),
        ("award", 2), ("expert", 2), ("professional", 1), ("reliable", 2),
    ],
    "fear": [
        # Japanese - spec required
        ("\u5371\u967a", 3),          # 危険
        ("\u653e\u7f6e", 2),          # 放置
        ("\u624b\u9045\u308c", 3),    # 手遅れ
        ("\u60aa\u5316", 2),          # 悪化
        ("\u75c5\u6c17", 2),          # 病気
        ("\u6b7b", 3),                # 死
        ("\u6700\u60aa", 2),          # 最悪
        ("\u53d6\u308a\u8fd4\u3057", 2),  # 取り返し
        ("\u6016\u3044", 3),          # 怖い
        ("\u30e4\u30d0\u3044", 2),    # ヤバい
        # Additional Japanese
        ("\u6050\u6016", 3),          # 恐怖
        ("\u8b66\u544a", 3),          # 警告
        ("\u8981\u6ce8\u610f", 2),    # 要注意
        ("\u30ea\u30b9\u30af", 2),    # リスク
        ("\u5931\u3046", 2),          # 失う
        ("\u5931\u6557", 2),          # 失敗
        ("\u5f8c\u6094", 3),          # 後悔
        ("\u653e\u7f6e\u3059\u308b\u3068", 3),  # 放置すると
        ("\u8870\u3048", 2),          # 衰え
        ("\u52a3\u5316", 2),          # 劣化
        ("\u8001\u3051", 2),          # 老け
        ("\u30c0\u30e1\u30fc\u30b8", 2),  # ダメージ
        # English
        ("danger", 3), ("warning", 3), ("risk", 2), ("lose", 2),
        ("regret", 3), ("too late", 3), ("damage", 2), ("fear", 3),
    ],
}


# ---------------------------------------------------------------------------
# Analysis logic
# ---------------------------------------------------------------------------

def _build_text(ad: Ad) -> str:
    """Build searchable text from ad fields."""
    parts = []
    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)

    meta = ad.ad_metadata or {}
    for key in ("body", "link_title", "link_description", "cta_text"):
        val = meta.get(key)
        if val and isinstance(val, str):
            parts.append(val)

    ca = meta.get("creative_analysis", {})
    if ca:
        for key in ("offer_detail", "headline"):
            val = ca.get(key)
            if val and isinstance(val, str):
                parts.append(val)

    return " ".join(parts)


def analyze_emotion(ad: Ad) -> dict:
    """Analyze emotion for a single ad.

    Returns: {"dominant": str, "scores": {emotion: int, ...}, "intensity": str}
    """
    text = _build_text(ad)
    text_lower = text.lower()

    if not text.strip():
        return {
            "dominant": "neutral",
            "scores": {e: 0 for e in EMOTION_KEYWORDS},
            "intensity": "none",
        }

    # Score each emotion
    raw_scores: dict[str, float] = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        total_weight = 0
        match_count = 0
        for keyword, weight in keywords:
            kw_lower = keyword.lower()
            if kw_lower in text_lower:
                total_weight += weight
                match_count += 1
        raw_scores[emotion] = total_weight

    max_raw = max(raw_scores.values()) if raw_scores else 0

    # Normalize to 0-100 scale
    # Max possible raw score is ~30+ for a single emotion (if all keywords match)
    # We use a softer normalization: score = min(100, raw * 100 / 15)
    scores: dict[str, int] = {}
    for emotion, raw in raw_scores.items():
        normalized = min(100, int(raw * 100 / 15)) if raw > 0 else 0
        scores[emotion] = normalized

    # Determine dominant emotion
    if max_raw == 0:
        dominant = "neutral"
    else:
        dominant = max(raw_scores, key=lambda e: raw_scores[e])

    # Intensity level
    dominant_score = scores.get(dominant, 0)
    if dominant_score >= 60:
        intensity = "strong"
    elif dominant_score >= 30:
        intensity = "moderate"
    elif dominant_score > 0:
        intensity = "weak"
    else:
        intensity = "none"

    return {
        "dominant": dominant,
        "scores": scores,
        "intensity": intensity,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("EMOTION ANALYSIS (Keyword-based)")
    print("Executed at: %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("Total ads in database: %d" % total)

        if total == 0:
            print("No ads found. Exiting.")
            return

        emotion_counter: Counter = Counter()
        intensity_counter: Counter = Counter()
        score_accumulators: dict[str, list[int]] = {e: [] for e in EMOTION_KEYWORDS}
        updated = 0

        for ad in ads:
            result = analyze_emotion(ad)

            meta = dict(ad.ad_metadata or {})
            meta["emotion_analysis"] = result
            meta["emotion_analyzed_at"] = datetime.now(timezone.utc).isoformat()
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            emotion_counter[result["dominant"]] += 1
            intensity_counter[result["intensity"]] += 1

            for e, s in result["scores"].items():
                score_accumulators[e].append(s)

            updated += 1

        session.commit()
        print("\nAnalyzed %d/%d ads. Committed." % (updated, total))

        # Print emotion distribution
        print("\n--- Dominant Emotion Distribution ---")
        for emotion, count in sorted(emotion_counter.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = "#" * int(pct / 2)
            print("  %-12s %5d (%5.1f%%) %s" % (emotion, count, pct, bar))

        # Print intensity distribution
        print("\n--- Intensity Distribution ---")
        for intensity, count in sorted(intensity_counter.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = "#" * int(pct / 2)
            print("  %-12s %5d (%5.1f%%) %s" % (intensity, count, pct, bar))

        # Print average scores per category
        print("\n--- Average Scores per Category ---")
        for emotion in EMOTION_KEYWORDS:
            vals = score_accumulators[emotion]
            avg = sum(vals) / len(vals) if vals else 0
            bar = "#" * int(avg / 2)
            print("  %-12s avg=%5.1f %s" % (emotion, avg, bar))

        # Print emotion co-occurrence (top scores per dominant emotion)
        print("\n--- Average Scores by Dominant Emotion ---")
        emotion_scores: dict[str, list[dict]] = {}
        for ad in ads:
            ea = (ad.ad_metadata or {}).get("emotion_analysis", {})
            dom = ea.get("dominant", "neutral")
            sc = ea.get("scores", {})
            if dom not in emotion_scores:
                emotion_scores[dom] = []
            emotion_scores[dom].append(sc)

        for dom in sorted(emotion_scores.keys()):
            entries = emotion_scores[dom]
            if not entries:
                continue
            avg_per_emotion = {}
            for e in EMOTION_KEYWORDS:
                vals = [entry.get(e, 0) for entry in entries]
                avg_per_emotion[e] = sum(vals) / len(vals) if vals else 0
            top_str = ", ".join(
                "%s=%.0f" % (e, v)
                for e, v in sorted(avg_per_emotion.items(), key=lambda x: -x[1])[:3]
            )
            print("  %-12s (n=%d) avg: %s" % (dom, len(entries), top_str))

        # Summary
        neutral_count = emotion_counter.get("neutral", 0)
        print("\n--- Summary ---")
        print("  Total analyzed:   %d" % total)
        print("  With emotion:     %d (%.1f%%)" % (
            total - neutral_count,
            (total - neutral_count) / total * 100 if total else 0
        ))
        print("  Neutral (no match): %d (%.1f%%)" % (
            neutral_count,
            neutral_count / total * 100 if total else 0
        ))
        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("FATAL ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
