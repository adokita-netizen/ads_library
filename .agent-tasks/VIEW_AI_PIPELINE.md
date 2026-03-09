# AI/ML パイプライン視点 — AI機能の接続状態と依存関係

## VAAP の AI/ML 機能マップ

```
                    ┌─────────────────────────┐
                    │     外部AI API          │
                    │  OpenAI / Anthropic     │
                    └───────┬─────────────────┘
                            │
            ┌───────────────┼───────────────────┐
            ▼               ▼                   ▼
    ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐
    │ コピー生成   │ │ スクリプト   │ │ AI専門家チャット │
    │ copy_gen.py  │ │ script_gen.py│ │ AIExpertView     │
    └──────────────┘ └──────────────┘ └─────────────────┘

                    ┌─────────────────────────┐
                    │     ローカルML          │
                    │  PyTorch / sklearn      │
                    └───────┬─────────────────┘
                            │
    ┌───────────────┬───────┼───────┬───────────────┐
    ▼               ▼       ▼       ▼               ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│ YOLOv8 │ │ Whisper│ │ BERT/  │ │ fatigue│ │ hit      │
│ 物体   │ │ 書起し │ │ NLP    │ │ 検知   │ │ 予測     │
│ 検出   │ │        │ │ 感情   │ │        │ │          │
└────────┘ └────────┘ └────────┘ └────────┘ └──────────┘
```

---

## 機能別の接続状態

### 1. クリエイティブ生成（外部API依存）

| 機能 | サービス | API | 状態 |
|------|---------|-----|------|
| 広告コピー生成 | copy_generator.py | OpenAI GPT-4 or Anthropic Claude | ⚠️ APIキー未設定 |
| 動画スクリプト生成 | script_generator.py | OpenAI GPT-4 or Anthropic Claude | ⚠️ APIキー未設定 |
| ストーリーボード生成 | creative_engine.py | OpenAI + Diffusers | ⚠️ APIキー未設定 |
| LP コピー最適化 | creative_engine.py | OpenAI or Anthropic | ⚠️ APIキー未設定 |

**必要なAPIキー**:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

**設定方法**: `/api/v1/settings/api-keys` API or DB直接

**コスト見積もり**:
- GPT-4: ~$0.03/1K tokens → 1生成あたり ~$0.10-0.30
- Claude: ~$0.015/1K tokens → 1生成あたり ~$0.05-0.15
- 月100回生成 → $5-30/月

### 2. Computer Vision（ローカルML — Worker依存）

| 機能 | サービス | モデル | 状態 |
|------|---------|--------|------|
| 物体検出 | object_detector.py | YOLOv8 | ⚠️ Worker未テスト |
| シーン検出 | scene_detector.py | scenedetect | ⚠️ Worker未テスト |
| OCR (テキスト) | ocr_engine.py | easyocr | ⚠️ Worker未テスト |
| 色分析 | color_analyzer.py | scikit-image | ⚠️ Worker未テスト |
| 構図分析 | composition_analyzer.py | OpenCV | ⚠️ Worker未テスト |

**動作条件**: ECS Fargate Worker で実行（Lambda では不可能）
**メモリ要件**: YOLOv8 → 2GB+, easyocr → 1GB+
**現在の ECS 設定**: 2048-8192 MB → 十分

### 3. Audio/NLP（ローカルML — Worker依存）

| 機能 | サービス | モデル | 状態 |
|------|---------|--------|------|
| 音声書き起こし | transcriber.py | OpenAI Whisper | ⚠️ Worker未テスト |
| 感情分析 | sentiment_analyzer.py | Transformers | ⚠️ Worker未テスト |
| キーワード抽出 | keyword_extractor.py | Fugashi + MeCab | ⚠️ Worker未テスト |

**特記**: Whisper は GPU なしでも動くが遅い（30秒動画 → 数分）

### 4. 予測モデル（ローカルML）

| 機能 | サービス | モデル | 状態 |
|------|---------|--------|------|
| ヒット予測 | performance_predictor.py | sklearn/XGBoost | ⚠️ 学習データ不足 |
| 疲労検知 | fatigue_detector.py | ルールベース + sklearn | ⚠️ 時系列データなし |
| 特徴量エンジニアリング | feature_engineering.py | 31特徴量 | ⚠️ 入力データ不足 |

**問題**: 58件ではML学習が意味をなさない。最低500件必要。

### 5. LP分析（Playwright依存）

| 機能 | サービス | 依存 | 状態 |
|------|---------|------|------|
| LP クロール | lp_crawler.py | Playwright/Selenium | ⚠️ Worker未テスト |
| LP コンテンツ分析 | lp_content_analyzer.py | BeautifulSoup + NLP | ⚠️ 未実行 |
| LP 比較 | lp_comparator.py | テキスト類似度 | ⚠️ データなし |
| 競合LP追跡 | competitor_intelligence.py | 定期クロール | ⚠️ 未稼働 |

### 6. 埋め込み/類似度（ベクトル検索）

| 機能 | サービス | モデル | 状態 |
|------|---------|--------|------|
| 広告テキスト埋め込み | embedding_service.py | sentence-transformers | ⚠️ 未実行 |
| 類似広告検索 | competitive/ | コサイン類似度 | ⚠️ 埋め込み未計算 |

---

## AI機能の優先度（プロダクト価値順）

### Tier 1: すぐ有効化できて価値が高い
1. **広告コピー生成** — APIキー設定のみで動く
2. **スクリプト生成** — 同上
3. **AI専門家チャット** — 同上

### Tier 2: Worker デプロイ後に有効化
4. **LP クロール・分析** — Playwright + NLP
5. **動画書き起こし** — Whisper（GPU不要だが遅い）
6. **物体検出** — YOLOv8（広告クリエイティブ分析）

### Tier 3: データ蓄積後に有効化
7. **ヒット予測モデル** — 500件以上のデータが必要
8. **疲労検知** — 時系列データ（ad_metrics）が必要
9. **類似広告検索** — 埋め込み計算が必要

### Tier 4: 本格運用後
10. **競合LP追跡** — 定期クロール運用
11. **広告テキスト感情分析** — 日本語モデル精度要検証

---

## AI機能有効化の手順

### Step 1: APIキー設定 (5分)
```bash
# DB経由で設定
curl -X POST "http://localhost:8000/api/v1/settings/api-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "openai_api_key": "sk-...",
    "anthropic_api_key": "sk-ant-..."
  }'

# 確認
curl "http://localhost:8000/api/v1/settings/api-keys"
```

### Step 2: フロントからテスト
1. 「クリエイティブ生成」ビューを開く
2. テーマを入力して「コピー生成」
3. レスポンスが返るか確認

### Step 3: Worker でのML機能テスト
```bash
# ローカルでWorkerを起動
cd C:/Users/ishit/ads_library
docker-compose up worker

# メディア分析タスクを投入
curl -X POST "http://localhost:8000/api/v1/ads/{ad_id}/analyze"
```

---

## AI/ML 依存パッケージの重さ

| パッケージ | サイズ | Lambda必要? | Worker必要? |
|-----------|--------|------------|------------|
| torch | ~800MB | ❌ 不要 | ✅ 必要 |
| transformers | ~400MB | ❌ 不要 | ✅ 必要 |
| whisper | ~1GB | ❌ 不要 | ✅ 必要 |
| ultralytics (YOLOv8) | ~200MB | ❌ 不要 | ✅ 必要 |
| easyocr | ~100MB | ❌ 不要 | ✅ 必要 |
| diffusers | ~300MB | ❌ 不要 | ✅ 必要 |
| openai | ~1MB | ✅ 軽い | ✅ 必要 |
| anthropic | ~1MB | ✅ 軽い | ✅ 必要 |
| playwright | ~50MB | ❌ 不要 | ✅ 必要 |

**結論**: Lambda には openai + anthropic + FastAPI のみ入れるべき。
重いML系は Worker (ECS Fargate) 専用。

**現在の Lambda**: requirements.txt に全部入り → コールドスタートが遅い原因。
**対策**: Lambda 用の `requirements-lambda.txt` を分離。
