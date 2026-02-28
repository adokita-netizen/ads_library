# Agent C タスク: ヒットパターン分析API

## 方向性
「なぜヒットしているのか」をAPIで返す。
Agent Aがad_metadataに記録する `creative_analysis` データを使って、
クリエイティブの勝ちパターンを可視化するためのAPIを構築する。

## 前提
Agent Aが各広告のad_metadataに以下を記録する（並行実行中）：
```python
ad_metadata["creative_analysis"] = {
    "hook_type": "question" | "pain_point" | ...,
    "cta_type": "purchase" | "signup" | ...,
    "offer_type": "discount" | "free" | ...,
    "offer_detail": "初回80%OFF" | None,
    "emotion": "fear" | "desire" | ...,
    "has_emoji": bool, "has_numbers": bool,
    "has_testimonial": bool, "has_before_after": bool,
    "text_length": "short" | "medium" | "long",
    "destination_type": "ec" | "lp" | "sns" | ...,
}
```

## やること

### 1. ヒット要因分析API
`GET /rankings/hit-factors`
- creative_analysisの各要素ごとにヒット率と平均スコアを集計
- レスポンス例:
```json
{
  "hook_type": {
    "question": {"count": 30, "hit_rate": 0.7, "avg_score": 65.2},
    "pain_point": {"count": 25, "hit_rate": 0.8, "avg_score": 72.1},
    ...
  },
  "cta_type": {...},
  "offer_type": {...},
  "emotion": {...},
  "winning_combinations": [
    {"hook": "pain_point", "cta": "consultation", "offer": "free", "hit_rate": 0.92, "count": 12}
  ]
}
```
- `winning_combinations`: ヒット率が最も高い要素の組み合わせトップ10

### 2. クリエイティブDNA API
`GET /rankings/creative-dna/{ad_id}`
- 個別広告のクリエイティブ分析詳細を返す
- creative_analysisの全フィールド + そのパターンの全体でのヒット率
```json
{
  "ad_id": 123,
  "creative_analysis": {...},
  "pattern_hit_rate": 0.75,  // 同じパターンの広告のヒット率
  "pattern_rank": 3,  // パターン強さ順位
  "similar_hits": [...]  // 同パターンのヒット広告トップ5
}
```

### 3. コピー分析API
`GET /rankings/copy-analysis`
- テキスト特徴の集計分析
```json
{
  "avg_description_length": {"hit": 250, "non_hit": 180},
  "emoji_usage": {"hit_with_emoji": 0.6, "hit_without_emoji": 0.4},
  "number_usage": {"hit_with_numbers": 0.75, "hit_without_numbers": 0.35},
  "testimonial_effect": {"hit_with_testimonial": 0.82, "hit_without": 0.45},
  "before_after_effect": {"hit_with_ba": 0.88, "hit_without": 0.42}
}
```

### 4. ジャンル別勝ちパターンAPI
`GET /rankings/genre-winning-patterns?genre=BEAUTY`
- 指定ジャンル内でのヒットパターン分析
- そのジャンル特有の勝ちパターンを返す

## 制約
- rankings.py に追加
- creative_analysisが未設定の広告は集計から除外
- ad_metadataの読み取りのみ（書き込まない — Agent A領域）
- 既存エンドポイントを壊さない
