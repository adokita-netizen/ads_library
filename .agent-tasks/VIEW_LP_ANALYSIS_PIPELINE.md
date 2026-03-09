# LP分析パイプライン視点 — 広告の先にあるLPまで追いかける

## なぜLP分析が重要か

- ヒット広告が分かっても「その先のLP」を見ないと全体像が見えない
- LP のCVR改善 = 広告ROI改善
- 競合のLP構成パターン → 自社LPの改善ヒント
- 広告テキスト × LPの整合性 = 品質スコアに影響

---

## LP分析の全体フロー

```
広告取得 (Meta API)
  ↓
destination_url 抽出
  ↓
LP クロール (Playwright)
  ├── スクリーンショット撮影
  ├── HTML取得
  ├── OGPメタデータ取得
  └── パフォーマンス計測
  ↓
LP 解析
  ├── テキスト抽出 → キーワード分析
  ├── 構成分析 → ヘッドライン/CTA/証拠/オファー検出
  ├── 画像分析 → ファーストビュー/商品画像
  └── 技術分析 → ページ速度/モバイル対応
  ↓
LP比較
  ├── 同一商材のLP A/B テスト検出
  ├── 競合LP間の比較
  └── 業界ベンチマーク
  ↓
レポート生成
```

---

## 既存のLP分析サービス

### backend/app/services/lp_analysis/

```
lp_crawler.py          → LP取得（Playwright使用）
lp_content_analyzer.py → コンテンツ分析
lp_comparator.py       → LP比較
competitor_intelligence.py → 競合インテリジェンス
```

### API エンドポイント

```
backend/app/api/endpoints/lp_analysis.py

推定エンドポイント:
  POST /api/v1/lp/analyze           → LP分析実行
  GET  /api/v1/lp/analysis/{id}     → 分析結果取得
  POST /api/v1/lp/compare           → LP比較
  GET  /api/v1/lp/competitors       → 競合LP一覧
```

---

## LP クロールの設計

### destination_url の取得元

```
1. Meta API の ad_creative_link_titles + ad_creative_link_captions
   → URL自体はsnapshot_urlからPlaywrightで抽出

2. ads テーブルの destination_url カラム
   → fix_destination_urls.py スクリプトで修復

3. ad_metadata の各種URL
   → landing_page_url
   → final_url（リダイレクト先）
```

### Playwright でのLP取得

```python
# services/lp_analysis/lp_crawler.py

class LPCrawler:
    async def crawl_lp(self, url: str) -> LPData:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 ...",
            )

            # リダイレクトを追跡
            redirects = []
            page.on("response", lambda r: redirects.append(r.url))

            # ページロード
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # 最終URL（リダイレクト後）
            final_url = page.url

            # スクリーンショット
            screenshot = await page.screenshot(full_page=True)

            # HTML取得
            html = await page.content()

            # OGPメタデータ
            og_data = await page.evaluate("""
                () => ({
                    title: document.querySelector('meta[property="og:title"]')?.content,
                    description: document.querySelector('meta[property="og:description"]')?.content,
                    image: document.querySelector('meta[property="og:image"]')?.content,
                })
            """)

            # パフォーマンス
            performance = await page.evaluate("""
                () => {
                    const timing = performance.timing;
                    return {
                        load_time: timing.loadEventEnd - timing.navigationStart,
                        dom_ready: timing.domContentLoadedEventEnd - timing.navigationStart,
                        first_paint: performance.getEntriesByType('paint')[0]?.startTime,
                    }
                }
            """)

            await browser.close()

            return LPData(
                url=url,
                final_url=final_url,
                redirects=redirects,
                html=html,
                screenshot=screenshot,
                og_data=og_data,
                performance=performance,
            )
```

---

## LP コンテンツ分析

### 分析項目

```
[構造分析]
- ファーストビュー: ヘッドライン + メインビジュアル
- ページ長: short(< 3000px), medium(3000-8000px), long(> 8000px)
- セクション数: div/section のカウント
- CTA数: ボタン/リンクのカウント
- フォーム有無: 入力フォームの存在

[テキスト分析]
- ヘッドライン: h1, h2 のテキスト
- キーワード: TF-IDFベースのキーワード抽出
- 証拠: 数字（「98%」「300万人」等）の抽出
- 緊急性: 「今だけ」「限定」「残りわずか」
- 特典: 「無料」「プレゼント」「送料無料」

[画像分析]
- 画像数
- ファーストビューの画像（商品 or 人物 or テキスト画像）
- 画像の合計サイズ（ページ速度に影響）

[技術分析]
- ページ読み込み時間
- モバイルフレンドリー度
- HTTPS対応
- カートシステム（Shopify, EC-CUBE等）
- 決済方法
- 計測タグ（Google Analytics, Meta Pixel等）
```

### 分析結果スキーマ

```json
{
  "ad_id": "abc123",
  "lp_url": "https://example.com/product",
  "final_url": "https://example.com/product?utm_source=fb",
  "analyzed_at": "2025-03-01T12:00:00Z",

  "structure": {
    "page_length_px": 5200,
    "page_type": "medium",
    "section_count": 8,
    "cta_count": 5,
    "has_form": true,
    "has_video": false,
    "image_count": 12
  },

  "content": {
    "headline": "たった1ヶ月で-5kg！驚きの新ダイエット法",
    "sub_headlines": ["科学的根拠", "お客様の声", "よくある質問"],
    "keywords": ["ダイエット", "痩せる", "1ヶ月", "サプリ"],
    "social_proof": {
      "numbers": ["98%", "300万人", "1ヶ月"],
      "testimonials_count": 5,
      "media_mentions": ["TV出演", "雑誌掲載"]
    },
    "urgency": ["今だけ", "限定500名", "本日23:59まで"],
    "offer": {
      "main": "初回980円",
      "bonus": "送料無料 + サプリケース付",
      "guarantee": "30日間返金保証"
    }
  },

  "technical": {
    "load_time_ms": 2300,
    "mobile_friendly": true,
    "https": true,
    "platform": "Shopify",
    "tracking": ["ga4", "meta_pixel", "line_tag"]
  },

  "score": {
    "overall": 78,
    "headline_strength": 85,
    "social_proof": 70,
    "urgency": 90,
    "offer_clarity": 75,
    "page_speed": 65
  }
}
```

---

## LP比較分析

### 同一広告主のLP比較（A/Bテスト検出）

```
同じ page_name のLPを比較:
  LP-A: https://example.com/product-a
  LP-B: https://example.com/product-b

比較項目:
  - ヘッドラインの違い
  - CTAの文言/色/位置
  - ページ長
  - オファー内容
  - どちらが長期配信されているか → 勝者推定
```

### ジャンル内LP比較

```
美容ジャンルのLP TOP10 を比較:
  - 共通パターン: ビフォーアフター → 証拠 → オファー → CTA
  - 差別化ポイント: 価格, 保証, 特典
  - ベンチマーク: 平均ページ長, 平均CTA数
```

---

## 広告 × LP の整合性分析

```
チェック項目:
  1. 広告のキーワード ⊂ LPのキーワード → 整合性高い
  2. 広告のオファー = LPのオファー → 一致必須
  3. 広告の画像/動画のトーン ≈ LPのトーン → ブランド一貫性
  4. 広告のCTA → LPのファーストビューに対応するCTAがあるか

整合性スコア:
  keyword_match: 80%  → 広告キーワードの80%がLPに存在
  offer_match: true   → オファーが一致
  tone_match: 0.75    → 視覚的トーンの類似度
  cta_alignment: true  → CTAの整合性
```

---

## データ保存

### lp_analyses テーブル

```sql
CREATE TABLE lp_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id UUID REFERENCES ads(id),
    url VARCHAR(2048) NOT NULL,
    final_url VARCHAR(2048),
    screenshot_s3_key VARCHAR(500),
    html_s3_key VARCHAR(500),        -- S3に保存（大きいので）
    analysis JSONB NOT NULL,          -- 分析結果
    score JSONB,                      -- スコア
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP              -- LP変更検知用
);

CREATE INDEX idx_lp_ad ON lp_analyses (ad_id);
CREATE INDEX idx_lp_url ON lp_analyses (url);
```

---

## フロント表示

### 広告詳細モーダル内のLPタブ

```
┌────────────────────────────────────────────┐
│ [基本情報] [メディア] [LP分析] [スコア詳細]  │
├────────────────────────────────────────────┤
│                                              │
│ LP URL: https://example.com/product         │
│ [サイトを開く ↗]                            │
│                                              │
│ ┌──────────────┐  ヘッドライン:             │
│ │              │  「たった1ヶ月で-5kg！」    │
│ │ スクリーン   │                            │
│ │ ショット    │  CTA: 5箇所                │
│ │              │  ページ長: 5200px          │
│ │              │  読み込み: 2.3秒            │
│ └──────────────┘                            │
│                                              │
│ LP スコア: 78/100                           │
│ ├── ヘッドライン: 85                        │
│ ├── 社会的証明: 70                          │
│ ├── 緊急性: 90                              │
│ ├── オファー: 75                            │
│ └── ページ速度: 65                          │
│                                              │
│ 検出キーワード:                              │
│ [ダイエット] [痩せる] [サプリ] [1ヶ月]      │
│                                              │
│ オファー: 初回980円 + 送料無料              │
│ 保証: 30日間返金保証                        │
└────────────────────────────────────────────┘
```

---

## 実装優先度

```
[Phase 1: 基本LP取得]
  1. destination_url の充実（fix_destination_urls.py 実行）
  2. LP スクリーンショット撮影（Playwright）
  3. 基本メタデータ取得（タイトル、OGP）
  4. 広告詳細にLPリンク表示

[Phase 2: コンテンツ分析]
  5. テキスト抽出 + キーワード分析
  6. 構造分析（セクション、CTA検出）
  7. LPスコアリング
  8. フロントのLPタブ

[Phase 3: 高度な分析]
  9. LP比較（A/Bテスト検出）
  10. 広告×LP整合性分析
  11. ジャンル別ベンチマーク
  12. LP変更トラッキング（定期再クロール）
```
