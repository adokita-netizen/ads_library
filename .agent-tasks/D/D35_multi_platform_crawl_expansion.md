# D35: マルチプラットフォーム・クロール拡張

## 概要
現在Meta中心のクロールを、YouTube・TikTok・X(Twitter)に拡張し、
クロスプラットフォームの広告データを安定的に収集する。

## 背景
VAAPは10プラットフォームのクローラーコードを持っているが、
実際に本番で安定動作しているのはMeta（Meta Ad Library API経由）のみ。
広告代理店の顧客は「YouTube・TikTok・Xの広告も見たい」と必ず要望する。
マルチプラットフォーム対応は競合との差別化の核心。

## タスク

### Task 1: YouTubeクローラーの本番化
```python
# backend/app/services/crawling/youtube_crawler.py (既存改修)

改修ポイント:
1. YouTube Data API v3 の正式統合
   - API_KEY を PlatformAPIKey テーブルから取得
   - search.list + videos.list の2段階取得
   - 広告検知ロジック: "Ad" タグ, Sponsored コンテンツ

2. YouTube Ads Transparency Center のスクレイピング
   - URL: https://adstransparency.google.com/
   - Playwright でJSレンダリング
   - 広告主名で検索 → 広告一覧を取得
   - 動画URL・サムネイル・配信期間を抽出

3. データマッピング:
   - platform = "youtube"
   - external_id = video_id
   - video_url = f"https://youtube.com/watch?v={video_id}"
   - thumbnail_url = maxres thumbnail
   - view_count, like_count = API から取得
   - creative_type = "video" (YouTubeは常に動画)

4. レート制限: YouTube API は 10,000 units/day
   - search.list = 100 units
   - videos.list = 1 unit per video
   - 1日あたり最大 ~95 searches + 詳細取得
```

### Task 2: TikTok クローラーの本番化
```python
# backend/app/services/crawling/tiktok_crawler.py (既存改修)

改修ポイント:
1. TikTok Commercial Content Library API
   - URL: https://library.tiktok.com/ads
   - 公開されている広告ライブラリからデータ取得
   - Playwright でページスクレイピング

2. データマッピング:
   - platform = "tiktok"
   - external_id = ad_id
   - video_url = 動画直リンク（Playwrightで抽出）
   - thumbnail_url = ポスター画像
   - creative_type = "video"

3. 日本向けフィルタリング:
   - country = "JP" でフィルタ
   - 日本語テキスト検出（タイトル/説明文のlang判定）

4. ページネーション対応:
   - スクロールベースのページング
   - 1リクエストあたり20件取得
   - 最大500件/セッション
```

### Task 3: X (Twitter) クローラーの本番化
```python
# backend/app/services/crawling/x_twitter_crawler.py (既存改修)

改修ポイント:
1. X Ads Transparency Center
   - URL: https://ads.x.com/transparency
   - 広告主名で検索
   - Playwright でJSレンダリング

2. データマッピング:
   - platform = "x"
   - creative_type = "image" / "video" / "carousel"
   - 広告テキスト、メディアURL、CTA

3. 日本語広告のフィルタリング:
   - ターゲット地域: Japan
   - 言語: ja
```

### Task 4: クロスプラットフォーム正規化
```python
# backend/app/services/crawling/normalizer.py (新規)

class AdNormalizer:
    """異なるプラットフォームの広告データを共通フォーマットに正規化する"""

    def normalize(self, platform: str, raw_data: dict) -> dict:
        """
        プラットフォーム固有のフォーマットを統一スキーマに変換:
        - title の最大長統一（500文字）
        - description のHTML→プレーンテキスト変換
        - 日付フォーマットの統一（ISO 8601）
        - メトリクスの単位統一（viewは全プラットフォーム共通）
        - creative_type の正規化（video/image/carousel/text）
        - ジャンル推定（タイトル+説明文からの自動分類）
        """

    def detect_cross_platform_duplicate(self, ad: dict, session) -> Optional[int]:
        """
        同一広告の異なるプラットフォーム版を検出:
        - 同一広告主名 + 類似タイトル（Levenshtein距離 < 0.3）
        - 同一destination_url
        → マッチしたらad_metadata に cross_platform_ids を記録
        """
```

### Task 5: プラットフォーム別ヘルスチェック
```python
# backend/app/services/crawling/platform_health.py (新規)

class PlatformHealthChecker:
    """各プラットフォームのクロール可否を定期チェックする"""

    async def check_all(self) -> dict:
        return {
            "meta": {
                "status": "healthy",      # healthy / degraded / down
                "api_token_valid": True,
                "last_successful_crawl": "2026-03-01T09:00:00",
                "error_rate_24h": 0.02,
            },
            "youtube": {
                "status": "degraded",
                "api_quota_remaining": 3200,
                "last_successful_crawl": "2026-03-01T06:00:00",
                "error_rate_24h": 0.15,
            },
            "tiktok": { ... },
            "x": { ... },
        }

    async def check_platform(self, platform: str) -> dict:
        """個別プラットフォームのヘルスチェック"""
        # 1. APIキー/トークンの有効性確認
        # 2. テストリクエストの送信
        # 3. レスポンスタイム計測
        # 4. エラー率の計算
```

## 完了条件
- [ ] YouTube クローラーが API + Transparency Center からデータを取得できる
- [ ] TikTok クローラーが Commercial Content Library からデータを取得できる
- [ ] X クローラーが Ads Transparency Center からデータを取得できる
- [ ] AdNormalizer が全プラットフォームのデータを統一フォーマットに変換する
- [ ] クロスプラットフォーム重複検出が動作する
- [ ] PlatformHealthChecker が各プラットフォームの状態を返す
- [ ] 全プラットフォームで日本語広告のフィルタリングが正しく動作する

## 触っていいファイル
- backend/app/services/crawling/youtube_crawler.py (改修)
- backend/app/services/crawling/tiktok_crawler.py (改修)
- backend/app/services/crawling/x_twitter_crawler.py (改修)
- backend/app/services/crawling/normalizer.py (新規)
- backend/app/services/crawling/platform_health.py (新規)
- backend/app/services/crawling/crawler_manager.py (統合)

## 注意
- 各プラットフォームの利用規約を遵守すること
- スクレイピングはAds Transparency系の公開ページに限定
- APIキーは PlatformAPIKey テーブルで管理（直接ハードコーディングNG）
- robots.txt を確認し、許可されたパスのみクロール
