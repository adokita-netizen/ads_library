# バックエンドアーキテクチャ視点 — サービス層の構造と改善点

## 全体構成

```
Lambda (API入口)
  └── FastAPI app (main.py)
        ├── Middleware
        │     ├── CORS
        │     ├── Request Timing
        │     └── Prometheus (optional)
        ├── Exception Handlers
        │     ├── ValidationError → 422
        │     ├── DatabaseError → 503
        │     └── Generic → 500
        └── Routers (12個)
              ├── auth.py
              ├── ads.py
              ├── campaigns.py
              ├── creative.py
              ├── rankings.py        ← 14,779行 (問題)
              ├── analytics.py
              ├── meta_marketing.py
              ├── competitive_intel.py
              ├── lp_analysis.py
              ├── media.py           ← 99,578行 (問題)
              ├── predictions.py
              ├── notifications.py
              └── settings.py
```

---

## サービス層の依存関係

```
endpoints (API層)
  ↓ 呼び出し
services (ビジネスロジック層)
  ├── ranking/
  │     └── ranking_service.py     ← ヒットスコア計算
  ├── crawling/
  │     ├── crawler_manager.py     ← クローラー統合
  │     ├── meta_crawler.py        ← Meta広告取得
  │     ├── youtube_crawler.py     ← YouTube広告取得
  │     └── ... (8個のクローラー)
  ├── cv/
  │     ├── video_analyzer.py      ← 動画分析統合
  │     ├── frame_extractor.py     ← フレーム抽出
  │     ├── scene_detector.py      ← シーン検出
  │     ├── object_detector.py     ← 物体検出 (YOLOv8)
  │     ├── ocr_engine.py          ← テキスト抽出
  │     ├── color_analyzer.py      ← 色分析
  │     └── composition_analyzer.py ← 構図分析
  ├── audio/
  │     ├── transcriber.py         ← Whisper書き起こし
  │     ├── audio_analyzer.py      ← 音声分析
  │     ├── sentiment_analyzer.py  ← 感情分析
  │     └── keyword_extractor.py   ← キーワード抽出
  ├── generative/
  │     ├── creative_engine.py     ← 生成統合
  │     ├── copy_generator.py      ← コピー生成
  │     └── script_generator.py    ← スクリプト生成
  ├── lp_analysis/
  │     ├── lp_crawler.py          ← LP取得
  │     ├── lp_content_analyzer.py ← コンテンツ分析
  │     ├── lp_comparator.py       ← LP比較
  │     └── competitor_intelligence.py
  ├── meta_marketing/
  │     ├── client.py              ← Graph API
  │     ├── token_manager.py       ← トークン管理
  │     ├── sync_service.py        ← 同期
  │     ├── campaign_manager.py    ← キャンペーン
  │     ├── optimizer.py           ← 最適化
  │     ├── ab_test_service.py     ← A/Bテスト
  │     ├── insights_engine.py     ← インサイト
  │     └── creative_analyzer.py   ← クリエイティブ分析
  ├── competitive/
  │     ├── embedding_service.py   ← ベクトル埋め込み
  │     ├── spend_estimator.py     ← 消化額推定
  │     ├── trend_predictor.py     ← トレンド予測
  │     ├── alert_detector.py      ← アラート検出
  │     └── destination_analytics.py ← LP分析
  ├── prediction/
  │     ├── performance_predictor.py ← パフォーマンス予測
  │     ├── fatigue_detector.py    ← 疲労検知
  │     └── feature_engineering.py ← 31特徴量
  ├── media_extraction.py          ← メディア抽出 (Playwright)
  └── thumbnail_fetcher.py         ← サムネイル取得
```

---

## 問題 1: rankings.py の責務過多

### 14,779行に含まれる機能群
```
ランキング計算    → ranking/ に委譲すべき
ダッシュボード集計 → analytics/ に委譲すべき
検索・フィルター  → search/ サービスを作るべき
エクスポート      → export/ サービスを作るべき
クロールトリガー  → crawling/ に委譲すべき
シナリオ生成      → generative/ に委譲すべき
ブックマーク管理  → models層で完結すべき
ユーザー設定      → settings に移すべき
```

### 理想的な分離
```python
# rankings.py (スリム化後)
from app.services.ranking import RankingService
from app.services.dashboard import DashboardService
from app.services.search import SearchService
from app.services.export import ExportService

@router.get("/pro-ranking")
async def pro_ranking(filters: RankingFilters, db: Session):
    return RankingService(db).get_pro_ranking(filters)

@router.get("/dashboard-summary")
async def dashboard(db: Session):
    return DashboardService(db).get_summary()
```

---

## 問題 2: media.py が 99,578行

### なぜこんなに大きいか（推定）
- バイナリデータ処理のヘルパー関数が大量
- メディアストリーミングの各形式対応
- Base64エンコード/デコード
- S3操作のラッパー
- 画像リサイズ/変換

### 確認すべき
```bash
# 行数確認
wc -l backend/app/api/endpoints/media.py

# エンドポイント数確認
grep -c "@router\." backend/app/api/endpoints/media.py
```

---

## 問題 3: 同期/非同期の混在

### Lambda (API) — 非同期
```python
# FastAPI のエンドポイントは async
@router.get("/rankings/pro-ranking")
async def pro_ranking():
    # しかし DB アクセスは SyncSessionLocal (同期)
    session = SyncSessionLocal()
    results = session.query(Ad).all()  # ブロッキング
```

### Worker (ECS) — 同期 + 非同期混在
```python
# media_tasks.py
def extract_media_task(ad_id):
    # 同期関数内から非同期を呼ぶ
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        extractor.extract(url, use_playwright=True)
    )  # イベントループの二重起動リスク
```

### 改善案
```python
# Lambda: async DB session を使う
from app.core.database import AsyncSessionLocal

@router.get("/rankings/pro-ranking")
async def pro_ranking():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Ad).where(...))
        return result.scalars().all()

# Worker: 完全に同期 or 完全に非同期に統一
# 同期に統一する場合:
from playwright.sync_api import sync_playwright
```

---

## 問題 4: データアクセスパターン

### N+1 クエリ（rankings.py で頻発の可能性）
```python
# ❌ N+1 パターン
rankings = session.query(ProductRanking).limit(20).all()
for r in rankings:
    ad = session.query(Ad).get(r.ad_id)  # 20回のクエリ
    r.title = ad.title

# ✅ JOIN パターン
results = session.query(ProductRanking, Ad)\
    .join(Ad, ProductRanking.ad_id == Ad.id)\
    .limit(20).all()
```

### 全件ロード（dashboard-summary で確認済み）
```python
# ❌ 全件ロードしてPythonで集計
ads = session.query(Ad).all()
total = len(ads)
active = sum(1 for a in ads if a.ad_metadata.get('is_still_running'))

# ✅ SQLで集計
from sqlalchemy import func, case
result = session.query(
    func.count(Ad.id).label('total'),
    func.count(case((Ad.status == 'active', 1))).label('active'),
).first()
```

---

## 問題 5: エラーハンドリングの層

### 現状（推定）
```
エンドポイント → try/except → 500 or 特定エラー
```

### 理想
```
エンドポイント
  ↓ (バリデーション) → 422 Validation Error (Pydantic自動)
  ↓
サービス層
  ↓ (ビジネスロジックエラー) → カスタム例外 → 400/404
  ↓
データ層
  ↓ (DB エラー) → DatabaseError → 503
  ↓
グローバルハンドラー
  → 未処理例外 → 500 (ログ付き)
```

### カスタム例外の導入
```python
# app/core/exceptions.py
class AppError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN", status: int = 400):
        self.message = message
        self.code = code
        self.status = status

class NotFoundError(AppError):
    def __init__(self, resource: str, id: any):
        super().__init__(f"{resource} {id} not found", "NOT_FOUND", 404)

class DataError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "DATA_ERROR", 422)

# main.py
@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}}
    )
```

---

## サービス間の依存関係図

```
ranking_service
  ├── depends on: Ad model, ProductRanking model
  ├── reads: ad_metadata (Agent A/D が書いたデータ)
  └── writes: product_rankings, ad_metadata.latest_hit_score

spend_estimator
  ├── depends on: Ad model, ad_metrics
  └── writes: 推定消化額

trend_predictor
  ├── depends on: ad_metrics (時系列)
  └── writes: velocity, acceleration

media_extraction (MediaExtractor)
  ├── depends on: playwright, httpx
  ├── reads: snapshot_url
  └── writes: video_url, image_url, thumbnail_url

copy_generator
  ├── depends on: openai or anthropic SDK
  ├── reads: Ad model (タイトル、テキスト)
  └── returns: 生成テキスト（DBに保存しない）
```

---

## 改善優先度

```
[今すぐ]
1. rankings.py 内のインラインロジックをサービス層に委譲
2. N+1 クエリの解消（JOIN化）
3. 全件ロードの SQL 集計化

[1ヶ月以内]
4. rankings.py の分割（コアランキング / ダッシュボード / 検索 / エクスポート）
5. 非同期/同期の統一
6. カスタム例外の導入

[3ヶ月以内]
7. media.py の分割・軽量化
8. キャッシュ層の導入 (Redis)
9. DB マイグレーション管理の厳格化
```
