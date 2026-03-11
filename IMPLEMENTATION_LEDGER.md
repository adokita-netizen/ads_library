# VAAP Implementation Ledger — Meta Ad Library Reference Architecture

> **最終更新**: 2026-03-11 (全タスク実装セッション)
> **目的**: 参照アーキテクチャに基づく実装台帳。途中から再開できるように現状・残課題・優先度を管理する。
> **読み方**: 各フェーズの `[x]` = 完了、`[-]` = 部分完了、`[ ]` = 未着手

---

## 0. Quick Resume Guide (ここから読め)

### 現在のインフラ状況
| リソース | 値 | 状態 |
|---------|---|------|
| CloudFront URL | `https://d3qlbagx7gq5sp.cloudfront.net` | OK |
| API Gateway | `https://j2wpopuxv4.execute-api.ap-northeast-1.amazonaws.com` | OK |
| Lambda | `vaap-production-api` | 稼働中 |
| RDS | `vaap-production-db.cxwsa6mgcgg6.ap-northeast-1.rds.amazonaws.com` | OK |
| S3 Frontend | `vaap-production-frontend` | OK |
| S3 Storage | `vaap-production-storage` | OK |
| ECR | `vaap-production-api`, `vaap-production-worker` | OK |
| SQS | `vaap-production-heavy-tasks`, `vaap-production-light-tasks` | OK |

### デプロイ手順
```bash
# Backend Lambda
cd /c/Users/ishit/ads_library
docker build --provenance=false -f docker/Dockerfile.lambda -t vaap-lambda .
docker tag vaap-lambda:latest 271669411511.dkr.ecr.ap-northeast-1.amazonaws.com/vaap-production-api:latest
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin 271669411511.dkr.ecr.ap-northeast-1.amazonaws.com
docker push 271669411511.dkr.ecr.ap-northeast-1.amazonaws.com/vaap-production-api:latest
aws lambda update-function-code --function-name vaap-production-api --image-uri 271669411511.dkr.ecr.ap-northeast-1.amazonaws.com/vaap-production-api:latest --region ap-northeast-1

# Frontend
cd frontend && rm -rf src/app/api out .next
NEXT_OUTPUT=export npm run build
aws s3 sync out/ s3://vaap-production-frontend/ --delete
aws cloudfront create-invalidation --distribution-id ERPIU1B8ZZ5ZA --paths "/*"

# DB Migration (Docker不要の緊急手段)
# pg8000 ZIPベース Lambda を作成し VPC内から ALTER TABLE 実行可能 (2026-03-11 実績あり)
```

### 直近の完了作業 (2026-03-11 全タスク実装)
- **H1**: Ad モデルに 9 新カラム追加 (ad_delivery_start/stop_time, publisher_platforms, estimated_audience_size_min/max, country_context, demographic_distribution, ad_creation_time, searchable_text)
- **H2**: Card builder 4配列正規化 (bodies/titles/captions/descriptions index合わせ)
- **H3**: LLM Angle 抽出 (Bedrock Claude) + ルールベース共存
- **H4**: Hit Proxy Score 参照アーキ6要素式 (active_days/recurrence/platform_spread/variant/consistency/capture_confidence)
- **H5**: Brand fuzzy matching (trigram Jaccard + substring + suffix stripping)
- **M1**: LP structure LLM 抽出 (lp_structure_extractor.py)
- **M2**: Creative Family phash + text similarity クラスタリング (Union-Find)
- **M3**: searchable_text 統合 + GIN tsvector index
- **M4**: Ad-to-LP consistency スコア (token Jaccard)
- **M5**: 訴求シェア集計 API + 月次トレンド API
- **L3**: Video timeline OCR+ASR 統合ビルダー
- **L5**: meta_creative_search_index マテビュー
- Lambda "enrich" アクション (全バッチ処理一括実行)
- 新 API: /appeal-share, /appeal-trends, /brand/{id}, /creative-families, /creative-family/{id}, /lp-snapshot/{card_id}, /batch/* (7エンドポイント)
- 新 Frontend ビュー: ブランド詳細、訴求マップ、クリエイティブ系統、訴求分析ダッシュボード (4 views, 30 views total)
- Frontend types + analyticsApi モジュール追加

---

## Phase 1: データ収集 & 保存 (Collection Layer)

### 1.1 Meta Ad Library ID 正規化
**目標**: `external_id` を `library_id` として統一し、参照アーキのキーにする

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] `external_id` を ads テーブルに保持 | `models/ad.py` | 完了 |
| [x] `ad_creation_time` を保存 | `models/ad.py` | 専用カラム追加済み |
| [x] `ad_delivery_start_time` / `ad_delivery_stop_time` 保存 | `models/ad.py` | 専用カラム追加済み |
| [x] `publisher_platforms` 配列保存 | `models/ad.py` | JSONB カラム追加済み |
| [x] `country_context` 保存 (検索条件) | `models/ad.py` | JSONB カラム追加済み |
| [x] `estimated_audience_size` min/max 保存 | `models/ad.py` | min/max 2カラム追加済み |
| [x] `demographic_distribution` 保存 | `models/ad.py` | JSONB 専用カラム追加済み |
| [-] `ad_snapshot_url` 専用カラム | `models/ad.py` | 現在 `snapshot_url` で代用中 |

**実装メモ**:
- `first_seen_at` / `last_seen_at` はクローラ側の観測日。`ad_delivery_start_time` は Meta 公式の配信開始日で別物
- `active_days` = `ad_delivery_stop_time - ad_delivery_start_time` が正確。現在は観測ベース

### 1.2 Ad Card 正規化 (カルーセル / マルチバージョン対応)
**目標**: Meta の `ad_creative_bodies[]`, `ad_creative_link_titles[]` 等を card_index で正規化

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] `ad_cards` テーブル作成 | `models/brand_registry.py` | 完了 |
| [x] `card_builder.py` サービス | `services/card_builder.py` | 完了。基本的なカード生成 |
| [x] Meta API からの配列 index 正規化 | `services/card_builder.py` | 4配列正規化実装済み (card_count = max of all arrays) |
| [x] `link_caption`, `link_description` 個別カラム | `models/brand_registry.py` | link_description カラムあり、caption は card_metadata に格納 |
| [ ] `capture_quality` カラム (full/partial/metadata_only) | `models/brand_registry.py` | 品質追跡 |
| [x] `ocr_text` / `asr_text` per card | `models/brand_registry.py` | カラム既存。card_builder で割り当て |
| [x] `initial_click_url` / `final_click_url` | `models/brand_registry.py` | destination_url_initial/final カラム既存 |
| [x] POST `/rankings/ad-cards/build` バッチ処理 | `api/endpoints/rankings.py` | 完了 |

**正規化ルール (参照アーキ)**:
```
card_count = max(len(bodies), len(titles), len(captions), len(descriptions))
足りない配列要素は NULL
```

### 1.3 Crawl インフラ
| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] Meta Ad Library API クローラ | `services/crawling/meta_crawler.py` | 完了 |
| [x] ジャンルローテーション (`get_today_keywords`) | `tasks/crawl_tasks.py` | 完了 |
| [x] `genre_keyword_packs` 20 ジャンル | `scripts/seed_genre_keyword_packs.py` | 完了 |
| [x] サムネイル即時 DL (fbcdn URL 有効期限対策) | `lambda_handler.py` | 完了 |
| [x] `ad_delivery_start/stop_time` フィールド取得 | `services/crawling/meta_crawler.py` | 取得済み・専用カラム保存済み |
| [x] `publisher_platforms` フィールド取得 | 同上 | 取得済み・専用カラム保存済み |
| [x] `estimated_audience_size` フィールド取得 | 同上 | 取得済み・min/max カラム保存済み |
| [x] `demographic_distribution` フィールド取得 | 同上 | 取得済み・JSONB カラム保存済み |
| [-] マルチプラットフォーム (TikTok, YouTube 等) | `services/crawling/` | スケルトンのみ。Meta 以外は実データなし |

---

## Phase 2: メディア抽出 & OCR/ASR (Extraction Layer)

### 2.1 OCR パイプライン
**目標**: 画像/動画フレームからテキスト抽出 → 構造化

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] EasyOCR エンジン (JA+EN) | `services/cv/ocr_engine.py` | 完了 |
| [x] フレーム単位 OCR + BBox | `models/analysis.py` (TextDetection) | 完了 |
| [ ] カード単位 `ocr_text` 統合 | `services/card_builder.py` | OCR結果を ad_cards.ocr_text に集約 |
| [ ] LP スクリーンショット OCR | 未実装 | LP画像内テキスト (hero, badge, price) |
| [ ] OCR 対象拡張 (参照アーキ準拠) | | hero画像内文字, testimonial画像, badge/award, comparison, before/after |

### 2.2 ASR パイプライン
**目標**: 動画音声 → テキスト化 → タイムライン統合

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] Whisper 音声書き起こし | `services/audio/transcriber.py` | 完了 |
| [x] セグメント単位タイミング | `models/analysis.py` (Transcription) | 完了 |
| [ ] カード単位 `asr_text` 統合 | `services/card_builder.py` | ASR結果を ad_cards.asr_text に集約 |
| [ ] UGC セリフ vs ナレーション分離 | 未実装 | speaker_id ベース |
| [ ] `video_timelines` への統合 | `models/brand_registry.py` | テーブルあり。OCR+ASR+visual_tags の時系列統合 |

### 2.3 メディアダウンロード & S3 保存
| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] サムネイル S3 保存 | `lambda_handler.py` | 完了 |
| [x] 画像 S3 保存 | `services/media_extraction.py` | 完了 |
| [-] 動画 S3 保存 | `services/media_extraction.py` | ECS Worker 必要。Lambda 15分制限 |
| [x] `creative_assets` テーブル | `models/creative_asset.py` | 完了 |
| [ ] `sha256` / `phash` ハッシュ計算 | `models/creative_asset.py` | カラムあり、計算ロジック未実装 |
| [ ] 重複メディア検出 (phash) | 未実装 | creative_family 統合に必要 |

---

## Phase 3: LLM 構造化抽出 (Intelligence Layer)

### 3.1 Angle Fact 抽出
**目標**: OCR/ASR/DOM テキストから訴求軸を構造化 JSON で抽出

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] ルールベース抽出 (JP キーワード辞書) | `services/angle_extractor.py` | 完了。10 hook_type, 12 pain, 8 offer, 9 proof |
| [x] `angle_facts` テーブル | `models/brand_registry.py` | 完了 |
| [x] POST `/rankings/angle-facts/extract` | `api/endpoints/rankings.py` | 完了 |
| [x] LLM 構造化抽出 (Claude/Bedrock) | `services/angle_extractor.py` | Bedrock Claude Haiku 実装済み。ルールベースとの共存 |
| [x] 出力スキーマ統一 (参照アーキ準拠) | `services/angle_extractor.py` | genre, primary_hook, cta 含む完全スキーマ |

**参照アーキ LLM 出力スキーマ**:
```json
{
  "genre": ["beauty", "hair_removal"],
  "hook_type": "scarcity",
  "primary_hook": "初回980円",
  "pain_points": ["自己処理が面倒"],
  "promises": ["短時間", "自宅完結"],
  "offer_types": ["first_discount"],
  "proof_types": ["doctor", "review"],
  "urgency_types": ["limited_time"],
  "audience_hints": ["female_30s"],
  "creative_styles": ["static", "direct_response"],
  "cta": "今すぐ診断"
}
```

**現在のルールベース vs LLM 比較**:
| 項目 | ルールベース (現在) | LLM (目標) |
|------|-------------------|-----------|
| hook_type | 10種 JP辞書マッチ | 文脈理解で判定 |
| pain_points | 12カテゴリ辞書 | 自由テキスト抽出 |
| offer_types | 8種辞書 | 価格/条件の意味理解 |
| proof_types | 9種辞書 | 証拠の種類と強度判定 |
| confidence | 辞書ヒット数ベース | LLM自己評価 |
| primary_hook | 未実装 | 最も強い訴求ワンライナー |
| cta | 未実装 | CTA テキスト抽出 |

### 3.2 LP 構造抽出
**目標**: LP HTML/DOM から構造化 JSON を抽出

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] LP クローラ (HTML取得, スクショ) | `services/lp_analysis/lp_crawler.py` | 完了 |
| [x] LP セクション分割 | `services/lp_analysis/lp_content_analyzer.py` | 完了 |
| [x] `lp_sections` テーブル | `models/landing_page.py` | 完了 |
| [x] `lp_snapshots` テーブル | `models/brand_registry.py` | 完了 |
| [x] `extracted_json` 構造化 | `services/lp_analysis/lp_structure_extractor.py` | LLM (Bedrock) + ルールベースフォールバック |
| [x] `lp_pattern` 自動判定 | `services/lp_analysis/lp_structure_extractor.py` | 8パターン自動判定 |
| [x] `claim_flags` 自動検出 | `services/lp_analysis/lp_structure_extractor.py` | 4フラグ自動検出 |
| [x] `conversion_type` 判定 | `services/lp_analysis/lp_structure_extractor.py` | lead/purchase/appointment/diagnosis |
| [x] `forms.field_labels` 抽出 | `services/lp_analysis/lp_structure_extractor.py` | LLM抽出 |

**参照アーキ LP 構造スキーマ**:
```json
{
  "lp_pattern": "quiz",
  "hero": { "headline": "", "subheadline": "", "primary_cta": "" },
  "offers": [], "prices": [], "benefits": [], "proofs": [],
  "urgencies": [], "faqs": [],
  "forms": { "present": true, "field_labels": [], "steps": 1 },
  "sections": [{ "section_type": "hero", "heading": "", "body": "", "cta": "" }],
  "conversion_type": "lead",
  "claim_flags": { "before_after": false, "doctor_supervised": false, "ranking_claim": false, "refund_guarantee": false }
}
```

### 3.3 Ad ↔ LP 一貫性スコア
**目標**: 広告訴求と LP hero の一致度を測定

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] `ad_to_lp_consistency_norm` 計算 | `services/ad_lp_consistency.py` | Token Jaccard 類似度 |
| [-] 価格一致チェック (広告「初回980円」= LP「初回980円」) | | consistency スコアに内包。数値特化は未実装 |
| [-] CTA 一致チェック | | consistency スコアに内包。CTA 特化は未実装 |

---

## Phase 4: Creative Family & Hit Proxy (Analytics Layer)

### 4.1 Creative Family (クリエイティブ統合)
**目標**: 同一訴求の広告バリエーションをファミリーにグルーピング

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] `creative_families` テーブル | `models/creative_asset.py` | 完了 |
| [x] `creative_assets` テーブル | `models/creative_asset.py` | 完了 |
| [x] phash ベース画像類似グルーピング | `services/creative_family_builder.py` | Hamming distance + Union-Find |
| [x] テキスト類似ベースグルーピング | `services/creative_family_builder.py` | Trigram Jaccard + Union-Find |
| [x] `family_id` 自動付与バッチ | `services/creative_family_builder.py` | build_creative_families() |
| [x] `variant_count`, `member_count` 集計 | `services/creative_family_builder.py` | update_family_stats() |

### 4.2 Hit Proxy Score (勝ち広告スコア)
**目標**: spend/CV が見えない中で「勝っている広告」を推定するプロキシスコア

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] `hit_proxy_score` カラム (ads) | `models/ad.py` | 完了 |
| [x] `avg_hit_proxy_score` (brand_registry) | `models/brand_registry.py` | 完了 |
| [x] スコア計算ロジック | `services/hit_proxy.py` | 参照アーキ6要素式実装済み |
| [x] 参照アーキ準拠の計算式実装 | `services/hit_proxy.py` | active_days/recurrence/platform/variant/consistency/capture |

**参照アーキ Hit Proxy Score 計算式**:
```
hit_proxy_score =
  0.35 * active_days_norm          # 長く回っている = 効果がある
+ 0.20 * recurrence_norm           # 同一訴求の繰り返し出稿
+ 0.15 * platform_spread_norm      # 複数プラットフォームに展開
+ 0.10 * variant_spread_norm       # バリエーション数
+ 0.10 * ad_to_lp_consistency_norm # 広告とLPの一貫性
+ 0.10 * capture_confidence_norm   # データ取得の信頼度
```

**必要な入力データ**:
| 指標 | 現在の取得状況 | 改善必要 |
|------|-------------|---------|
| `active_days` | 観測ベース (first_seen - last_seen) | `ad_delivery_start/stop_time` から計算 |
| `recurrence` | 未計算 | creative_family の member_count |
| `platform_spread` | 単一 platform | `publisher_platforms[]` 配列 |
| `variant_spread` | 未計算 | family 内の variant_count |
| `ad_to_lp_consistency` | 未実装 | Phase 3.3 |
| `capture_confidence` | 未実装 | OCR/ASR/LP 取得率 |

### 4.3 Brand Registry 強化
| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] ブランド自動発見 (advertiser_name 正規化) | `services/brand_resolver.py` | 完了。136 brands |
| [x] ドメイン自動検出 | `services/brand_resolver.py` | 完了 |
| [x] vertical 自動分類 | `services/brand_resolver.py` | 完了 (genre_tag ベース) |
| [-] `meta_page_ids` 自動紐付け | | page_id は metadata に保存済み。brand 自動紐付けは手動 |
| [x] 重複ブランド統合 (fuzzy match) | `services/brand_resolver.py` | Trigram Jaccard + substring + suffix matching |
| [-] ブランド名の正規化精度向上 | `services/brand_resolver.py` | prefix/suffix stripping 改善。LLM抽出は未実装 |

---

## Phase 5: 検索 & 発見 (Search Layer)

### 5.1 全文検索
| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] タイトル/説明文検索 | `api/endpoints/rankings.py` (proSearch) | 完了 |
| [x] `searchable_text` 統合カラム | `services/searchable_text_builder.py` | body + OCR + ASR + LP + angle facts 統合 |
| [x] PostgreSQL `tsvector` / `GIN` インデックス | `lambda_handler.py` | migrate action で自動作成 |
| [-] ファセット検索 (hook_type, offer_type, lp_pattern) | `api/endpoints/rankings.py` | proSearch に hook_type/offer_type あり。lp_pattern 未追加 |

### 5.2 ベクトル検索 (Semantic Search)
| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] 基本 embedding (hash ベース 128dim) | `services/competitive/embedding_service.py` | 完了。簡易実装 |
| [x] `ad_embeddings` テーブル (JSONB) | `models/competitive_intel.py` | 完了 |
| [ ] sentence-transformers / OpenAI embedding アップグレード | | 精度向上 |
| [ ] pgvector 拡張 | | ANN 検索高速化。現在は全件メモリロード |
| [ ] マルチモーダル embedding (text + image + video) | | 参照アーキ: text_embedding, image_embedding, video_embedding, lp_embedding |
| [ ] `meta_creative_search_index` 統合ビュー | | family 単位の検索インデックス |

### 5.3 参照アーキ検索インデックス (目標構造)
```sql
meta_creative_search_index (
  family_id       uuid PRIMARY KEY,
  brand_name      text,
  page_names      text[],
  library_ids     text[],
  publisher_platforms text[],
  media_types     text[],
  hook_types      text[],
  offer_types     text[],
  proof_types     text[],
  creative_styles text[],
  lp_patterns     text[],
  final_domains   text[],
  first_seen      timestamptz,
  last_seen       timestamptz,
  active_days     int,
  searchable_text text,
  text_embedding  vector,
  image_embedding vector,
  video_embedding vector,
  lp_embedding    vector
)
```

---

## Phase 6: 訴求分析 & 集計 (Analytics Layer)

### 6.1 訴求シェア分析
**目標**: 「どういう訴求が多いか」の集計

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] hook_type 分布集計 | `api/endpoints/rankings.py` (angle-stats) | 完了 |
| [x] offer_type 分布集計 | `api/endpoints/rankings.py` | /appeal-share API |
| [x] proof_type 分布集計 | 同上 | 同上 |
| [x] creative_style 分布集計 | 同上 | 同上 |
| [x] lp_pattern 分布集計 | 同上 | 同上 |
| [x] 期間/ジャンル/ブランド別クロス集計 | 同上 | hook_x_offer クロスタブ + genre/date フィルタ |
| [x] 時系列トレンド (月次推移) | 同上 | /appeal-trends API |

### 6.2 Taxonomy 定義
**参照アーキ Taxonomy** (完全版):

```yaml
genre:
  - beauty, health, finance, career, education, ecommerce, saas, app, entertainment

hook_type:
  - question, empathy, benefit_first, scarcity, authority,
    social_proof, comparison, before_after, shock

offer_type:
  - free_trial, first_discount, diagnosis, booking, bonus,
    free_shipping, refund, installment

proof_type:
  - review, testimonial, doctor, media_feature, ranking_claim,
    numbers_claim, ugc, expert_endorsement

creative_style:
  - static, ugc_video, founder_talk, testimonial_video,
    product_demo, slideshow, carousel, motion_graphics

lp_pattern:
  - quiz, lead_form, advertorial, direct_response_lp,
    comparison_lp, ecommerce_pdp, vsl_lp, appointment_lp
```

| タスク | ファイル | 状態 |
|-------|---------|------|
| [x] `genre_taxonomy` テーブル (階層) | `models/creative_asset.py` | 完了 |
| [x] `ad_genre_tags` テーブル | `models/creative_asset.py` | 完了 |
| [x] hook_type (11 定義済み) | `services/angle_extractor.py` | before_after 追加済み (11種) |
| [x] `before_after` hook_type 追加 | `services/angle_extractor.py` | 実装済み |
| [x] offer_type taxonomy 正式定義 | `services/angle_extractor.py` | LLM版: free_trial/first_discount/diagnosis/booking/bonus/free_shipping/refund/installment |
| [-] creative_style 自動分類 | `services/angle_extractor.py` | LLM版で8種対応。画像/動画自動判定は部分的 |

---

## Phase 7: フロントエンド強化 (UI Layer)

### 7.1 既存ビュー (26 views)
| ビュー | 状態 | バックエンド依存 |
|-------|------|--------------|
| PRO DATABASE | [x] 完了 | rankings API |
| 検索 | [x] 完了 | proSearch API |
| トレンド | [x] 完了 | metrics API |
| 分析 | [x] 完了 | analysis API |
| ヒートマップ | [x] 完了 | metrics API |
| LP分析 | [x] 完了 | lp-analysis API |
| 競合インテリジェンス | [x] 完了 | competitive-intel API |
| ヒット広告分析 | [x] 完了 | hit-ads API |
| AI チャット | [x] 完了 | ai-chat API |
| メディア管理 | [x] 完了 | media API |

### 7.2 新規必要ビュー
| ビュー | 目的 | 状態 |
|-------|------|------|
| [x] ブランド詳細 | `BrandDetailView.tsx` | API + UI 完了 |
| [x] 訴求マップ | `AppealMapView.tsx` | 分布 + クロスタブ + トレンド |
| [-] カード比較 | ad_cards の横並び比較 | API あり、専用 UI 未実装 (比較ツール内で対応可能) |
| [x] LP 構造ビューア | `/lp-snapshot/{card_id}` API | extracted_json 表示対応 |
| [x] Creative Family ビュー | `CreativeFamilyView.tsx` | 一覧 + 詳細 + フィルタ |
| [x] Angle Fact ダッシュボード | `AngleFactDashboard.tsx` | 全体俯瞰 + ランキング |

---

## Phase 8: 精度向上ロードマップ (Quality Upgrades)

### 優先度 HIGH (即効性あり) — **全完了**
| # | タスク | 状態 |
|---|-------|------|
| H1 | Meta API fields 追加 | **完了** — 9 新カラム + Lambda migrate |
| H2 | Card 正規化 (4配列 index 合わせ) | **完了** — card_builder.py 全面改修 |
| H3 | LLM Angle 抽出 (Claude/Bedrock) | **完了** — angle_extractor.py LLM + ルール共存 |
| H4 | Hit Proxy Score 参照アーキ準拠計算 | **完了** — 6要素式 hit_proxy.py |
| H5 | ブランド統合 fuzzy match | **完了** — brand_resolver.py trigram fuzzy |

### 優先度 MEDIUM (中期改善) — **全完了**
| # | タスク | 状態 |
|---|-------|------|
| M1 | LP extracted_json LLM 抽出 | **完了** — lp_structure_extractor.py |
| M2 | Creative Family phash グルーピング | **完了** — creative_family_builder.py Union-Find |
| M3 | searchable_text + tsvector 全文検索 | **完了** — searchable_text_builder.py + GIN index |
| M4 | ad_to_lp_consistency スコア | **完了** — ad_lp_consistency.py token Jaccard |
| M5 | 訴求シェア集計 API + UI | **完了** — /appeal-share, /appeal-trends + AppealMapView |

### 優先度 LOW (長期投資) — **一部完了**
| # | タスク | 状態 |
|---|-------|------|
| L1 | pgvector + sentence-transformers | 未着手 (RDS pgvector 拡張が必要) |
| L2 | マルチモーダル embedding (image+video) | 未着手 (L1 前提) |
| L3 | video_timelines OCR+ASR 統合 | **完了** — video_timeline_builder.py |
| L4 | LP スクリーンショット OCR | 未着手 (ECS Worker 前提) |
| L5 | meta_creative_search_index マテビュー | **完了** — Lambda migrate で自動作成 |

---

## Appendix A: DB テーブル一覧 (Production RDS)

### Core Tables (稼働中)
```
ads, ad_frames, ad_analyses, ad_daily_metrics, product_rankings,
users, campaigns, campaign_ads, platform_api_keys, landing_pages,
lp_sections, usp_patterns, appeal_axis_analyses, lp_analyses,
alert_rules, alert_history, alert_logs, crawl_jobs,
generated_creatives, creative_templates, conversations,
data_quality_snapshots, notification_configs, saved_items,
performance_predictions, ad_fatigue_logs, meta_ad_accounts
```

### Phase 1 Tables (稼働中)
```
creative_assets, creative_families, genre_taxonomy, ad_genre_tags
```

### Phase 2 Tables (2026-03-11 作成)
```
brand_registry, ad_cards, angle_facts, lp_snapshots,
genre_keyword_packs, video_timelines
```

### Analytics Tables (稼働中)
```
ad_embeddings, spend_estimates, cpm_calibrations,
lp_fingerprints, ad_classification_tags, lp_funnels,
funnel_steps, trend_predictions, ab_tests
```

## Appendix B: 重要ファイルパス
```
backend/
├── lambda_handler.py              # Lambda エントリ + migrate/crawl/cleanup/enrich actions
├── app/
│   ├── models/
│   │   ├── ad.py                  # Ad (9新カラム追加), AdFrame
│   │   ├── brand_registry.py      # BrandRegistry, AdCard, AngleFact, LPSnapshot, VideoTimeline, GenreKeywordPack
│   │   ├── creative_asset.py      # CreativeAsset, CreativeFamily, GenreTaxonomy, AdGenreTag
│   │   ├── competitive_intel.py   # AdEmbedding, SpendEstimate, LPFingerprint, AlertLog
│   │   └── landing_page.py        # LandingPage, LPSection, USPPattern
│   ├── services/
│   │   ├── angle_extractor.py     # ルールベース + LLM (Bedrock) 訴求抽出
│   │   ├── brand_resolver.py      # ブランド正規化 + fuzzy match
│   │   ├── card_builder.py        # AdCard 生成 (4配列正規化)
│   │   ├── hit_proxy.py           # Hit Proxy Score (参照アーキ6要素式)
│   │   ├── searchable_text_builder.py  # 統合検索テキスト生成 [NEW]
│   │   ├── ad_lp_consistency.py   # Ad-LP 一貫性スコア [NEW]
│   │   ├── creative_family_builder.py  # phash/text クラスタリング [NEW]
│   │   ├── video_timeline_builder.py   # 動画 OCR+ASR タイムライン [NEW]
│   │   ├── lp_analysis/
│   │   │   ├── lp_structure_extractor.py  # LP 構造 LLM 抽出 [NEW]
│   │   │   ├── lp_crawler.py
│   │   │   └── lp_content_analyzer.py
│   │   ├── analytics/
│   │   │   └── appeal_share_analyzer.py  # 訴求シェア集計 [NEW]
│   │   ├── cv/ocr_engine.py       # EasyOCR
│   │   ├── audio/transcriber.py   # Whisper ASR
│   │   └── competitive/embedding_service.py  # Embedding + 類似検索
│   └── api/endpoints/
│       ├── rankings.py            # 180+ エンドポイント (appeal-share/trends/brand/family/batch 追加)
│       ├── ads.py                 # 広告 CRUD (Meta fields 保存対応)
│       └── competitive_intel.py   # 競合分析 API

frontend/
├── src/
│   ├── app/page.tsx               # メイン SPA (30 views)
│   ├── lib/api.ts                 # API クライアント (13 modules, analyticsApi 追加)
│   ├── components/dashboard/
│   │   ├── BrandDetailView.tsx    # ブランド詳細 [NEW]
│   │   ├── AppealMapView.tsx      # 訴求マップ [NEW]
│   │   ├── CreativeFamilyView.tsx # クリエイティブ系統 [NEW]
│   │   ├── AngleFactDashboard.tsx # 訴求分析 [NEW]
│   │   └── (70+ 既存コンポーネント)
│   └── types/index.ts             # 型定義 (拡張: BrandDetail, CreativeFamily, AppealShare 等)
```

## Appendix C: 環境変数 (Lambda)
```
APP_ENV=production
DB_ENDPOINT=vaap-production-db.cxwsa6mgcgg6.ap-northeast-1.rds.amazonaws.com:5432
DB_NAME=vaap_db
DB_USERNAME=vaap
DB_SECRET_ARN=arn:aws:secretsmanager:ap-northeast-1:271669411511:secret:vaap-production/db-password-LJ87rf
AWS_S3_BUCKET=vaap-production-storage
STORAGE_BACKEND=s3
TASK_BACKEND=sqs
SQS_HEAVY_QUEUE_URL=https://sqs.ap-northeast-1.amazonaws.com/271669411511/vaap-production-heavy-tasks
SQS_LIGHT_QUEUE_URL=https://sqs.ap-northeast-1.amazonaws.com/271669411511/vaap-production-light-tasks
CORS_ORIGINS=https://d3qlbagx7gq5sp.cloudfront.net,http://localhost:3000
```
