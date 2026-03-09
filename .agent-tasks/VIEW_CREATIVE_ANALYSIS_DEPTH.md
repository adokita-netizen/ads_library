# クリエイティブ深層分析視点 — 動画広告の「なぜ売れるか」を解明する

## なぜクリエイティブ分析が核心か

- 「どの広告がヒットしているか」は分かる → ここまでは他ツールも可能
- 「なぜヒットしているか」を分析できる → VAAPの真の差別化ポイント
- 広告主が欲しいのは「次に作る広告の設計図」

---

## クリエイティブ分析の階層

```
Level 0: メタデータ分析（現在実装済み）
  → 配信期間、消化額、プラットフォーム
  → これだけでヒットスコアは計算可能

Level 1: テキスト分析（部分実装）
  → 広告テキスト（ad_creative_bodies）のキーワード
  → ヘッドライン分析
  → CTA 分析

Level 2: ビジュアル分析（サービス存在、未接続）
  → サムネイル/フレームの色分析
  → テキスト overlay の検出（OCR）
  → 人物の有無、表情

Level 3: 動画構造分析（サービス存在、未接続）
  → シーン分割（hook / body / CTA）
  → カット数、テンポ
  → モーション検出

Level 4: 音声分析（サービス存在、未接続）
  → 書き起こし（Whisper）
  → BGMの有無、ジャンル
  → ナレーション vs テロップ
  → 感情分析（声のトーン）

Level 5: パターン分析（未実装）
  → ヒット広告の共通パターン抽出
  → ジャンル × パターン のクロス分析
  → 「勝ちフォーミュラ」の自動生成
```

---

## 既存のCV/Audio サービス

### backend/app/services/cv/ （Computer Vision）

```
video_analyzer.py      → 統合分析エンジン
frame_extractor.py     → 動画からフレーム抽出
scene_detector.py      → シーン検出（カット検出）
object_detector.py     → 物体検出（YOLOv8）
ocr_engine.py          → テキスト検出（Tesseract or EasyOCR）
color_analyzer.py      → 色分析（支配色、配色パターン）
composition_analyzer.py → 構図分析（三分割法など）
```

### backend/app/services/audio/

```
transcriber.py         → 音声書き起こし（Whisper）
audio_analyzer.py      → 音声分析（BPM、音量）
sentiment_analyzer.py  → 感情分析（声のトーン）
keyword_extractor.py   → キーワード抽出
```

### 接続の課題

```
問題: これらのサービスは実装されているが、
     実際の広告データとのパイプラインが繋がっていない

必要なもの:
  1. 動画ファイルの取得（Playwright → 動画URL → ダウンロード）
  2. フレーム抽出のトリガー（Worker経由）
  3. 分析結果のDB保存先
  4. フロントでの分析結果表示
```

---

## 動画構造の分析フレームワーク

### 広告動画の3部構成

```
[Hook] 0-3秒
  目的: 視聴者の注意を引く
  分析:
    - ファーストフレームの内容（テキスト? 人物? 商品?）
    - テキストoverlay の内容（「衝撃」「驚き」「知ってた？」）
    - 音声の開始パターン（BGM? ナレーション? SE?）
    - カットの速度（速い = 注意引く）

[Body] 3-20秒
  目的: 商品/サービスの価値を伝える
  分析:
    - 情報の提示順序（問題提起 → 解決策 → 証拠 → CTA）
    - ビフォーアフターの有無
    - テスティモニアル（証言）の有無
    - 数字/データの使用（「98%の方が実感」）
    - テンポ（カット数/秒）

[CTA] 最後2-5秒
  目的: 行動を促す
  分析:
    - CTAの文言（「今すぐ購入」「詳しくはこちら」）
    - オファーの提示（「初回50%OFF」）
    - 緊急性（「残り10個」「今日だけ」）
    - 行動の具体性（「下のリンクをタップ」）
```

### 分析結果スキーマ

```json
{
  "ad_id": "abc123",
  "video_duration_seconds": 30,
  "analyzed_at": "2025-03-01T12:00:00Z",

  "structure": {
    "hook": {
      "duration_seconds": 3,
      "type": "question",
      "text_overlay": "知ってた？この方法で−5kg",
      "has_face": true,
      "dominant_color": "#FF5733",
      "attention_score": 85
    },
    "body": {
      "duration_seconds": 22,
      "scene_count": 8,
      "has_before_after": true,
      "has_testimonial": true,
      "has_data_proof": true,
      "information_flow": ["problem", "solution", "proof", "benefits"],
      "tempo": "medium"
    },
    "cta": {
      "duration_seconds": 5,
      "text": "今すぐチェック →",
      "offer": "初回限定 980円",
      "urgency": "本日23:59まで",
      "action_clarity": "high"
    }
  },

  "visual": {
    "dominant_colors": ["#FF5733", "#FFFFFF", "#333333"],
    "color_scheme": "warm",
    "text_overlay_ratio": 0.35,
    "face_count": 3,
    "product_shown": true,
    "animation_used": true,
    "aspect_ratio": "9:16"
  },

  "audio": {
    "has_narration": true,
    "has_bgm": true,
    "bgm_genre": "upbeat_pop",
    "narration_text": "多くの方が悩む...",
    "speech_speed": "medium",
    "emotion": "positive_excited",
    "keywords": ["悩み", "解決", "実感", "今だけ"]
  },

  "pattern_tags": [
    "question_hook",
    "before_after",
    "testimonial",
    "limited_offer",
    "ugc_style"
  ]
}
```

---

## パターン分類タクソノミー

### Hook パターン

```
question_hook     → 「知ってた？」「まだやってないの？」
shock_hook        → 衝撃的な映像/数字
curiosity_hook    → 「実は〇〇だった」
problem_hook      → 「こんな悩みありませんか？」
result_hook       → 「1ヶ月で-5kg」（結果先出し）
ugc_hook          → 一般人風の「これ最高だった」
celebrity_hook    → 有名人/インフルエンサー
text_only_hook    → テキストオーバーレイのみ
```

### Body パターン

```
problem_solution  → 問題 → 解決策
before_after      → ビフォーアフター
feature_benefit   → 特徴 → ベネフィット
storytelling      → ストーリー仕立て
demonstration     → 使用方法デモ
comparison        → 競合比較
testimonial       → ユーザー証言
scientific        → 科学的根拠/データ
```

### CTA パターン

```
direct_purchase   → 「今すぐ購入」
learn_more        → 「詳しくはこちら」
limited_offer     → 「今だけ○○%OFF」
free_trial        → 「無料で試す」
social_proof_cta  → 「○万人が選んだ」+ CTA
scarcity          → 「残りわずか」
guarantee         → 「返金保証付き」
```

---

## ジャンル × パターン クロス分析

### 分析テーブル

```
           | question | shock | ugc  | result | problem |
美容       |  35%     | 15%   | 25%  | 20%    | 5%      |
健康食品   |  20%     | 10%   | 15%  | 40%    | 15%     |
ダイエット |  25%     | 20%   | 20%  | 30%    | 5%      |
金融       |  15%     | 5%    | 10%  | 30%    | 40%     |
教育       |  30%     | 5%    | 15%  | 25%    | 25%     |

→ 「美容はquestion_hook + ugc が効果的」
→ 「健康食品はresult_hook が圧倒的」
→ 「金融はproblem_hookが多い」
```

### 勝ちフォーミュラ生成

```
ジャンル: 美容
プラットフォーム: Instagram

推奨フォーミュラ:
  Hook: question_hook (35%) or ugc_hook (25%)
  Body: before_after (40%) + testimonial (30%)
  CTA: limited_offer (45%)

例:
  「まだ知らないの？」(question_hook)
  → ビフォーアフター写真 (before_after)
  → 3名のユーザー証言 (testimonial)
  → 「今だけ初回980円」(limited_offer)

この組み合わせのヒット率: 推定65%（過去データから）
```

---

## 実装パイプライン

### Phase 1: テキスト分析の強化

```
1. ad_creative_bodies のキーワード抽出
2. フックパターンの自動分類（ルールベース）
3. CTAパターンの自動分類
4. 結果をad_metadataに保存
```

### Phase 2: 動画取得 + 基本ビジュアル分析

```
1. 動画URLの取得（Playwright → メディア抽出）
2. サムネイル分析（色、テキスト overlay、人物検出）
3. 動画のフレーム抽出（1秒1フレーム）
4. ファーストフレームの分析
```

### Phase 3: 動画構造分析

```
1. シーン検出（カット検出）
2. Hook/Body/CTA の3部構成分割
3. 各パートの分析
4. パターンタグ付け
```

### Phase 4: 音声分析

```
1. 動画から音声抽出
2. Whisper で書き起こし
3. BGM/ナレーション分離
4. 感情分析
```

### Phase 5: パターン分析 + レポート

```
1. ジャンル × パターン クロス集計
2. 勝ちフォーミュラ生成
3. フロント表示（HitAdAnalysisView に統合）
4. レポートエクスポート
```

---

## 必要なインフラ

```
動画ダウンロード: S3に一時保存（処理後削除 or Glacier）
フレーム抽出: ffmpeg（ECS Worker に追加）
OCR: Tesseract or EasyOCR（既にCV serviceに含まれる）
物体検出: YOLOv8（CPU推論 → 遅いがGPU不要）
音声書き起こし: Whisper small（CPU可、精度はmedium推奨）
感情分析: テキストベース or 音声ベース

コスト:
  ECS Worker の処理時間増加: 1広告あたり5-15分
  S3 一時保存: ~$1/月
  GPU なし → CPU推論: 遅いが無料
```
