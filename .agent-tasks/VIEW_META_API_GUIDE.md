# Meta API トークン取得ガイド — 最大のブロッカーを解除する

## なぜこれが最優先か

Meta APIトークンが無効 = 新しい広告をクロールできない = 全機能がデータ不足で機能しない。

---

## トークン取得手順

### Step 1: Meta for Developers にログイン
1. https://developers.facebook.com/ にアクセス
2. Facebook アカウントでログイン
3. 「マイアプリ」→ 既存アプリを選択 or 新規作成

### Step 2: アプリの設定
1. アプリタイプ: 「ビジネス」or 「なし」
2. 製品を追加: 「Marketing API」
3. アプリモード: 「開発中」でOK（自分のデータのみ）

### Step 3: アクセストークン取得

**方法 A: Graph API Explorer（最簡単）**
1. https://developers.facebook.com/tools/explorer/
2. アプリを選択
3. 「トークンを取得」→「ユーザーアクセストークン」
4. パーミッション追加:
   - `ads_read`
   - `ads_management`（自社広告管理する場合）
5. 「Generate Access Token」
6. トークンをコピー

**方法 B: 長期トークン（推奨）**
1. 短期トークンを取得（方法Aで）
2. 長期トークンに交換:
```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```
3. 返ってきた `access_token` が60日間有効

### Step 4: トークンの検証
```bash
# トークンの情報確認
curl "https://graph.facebook.com/v19.0/me?access_token=YOUR_TOKEN"

# Ad Library API テスト
curl "https://graph.facebook.com/v19.0/ads_archive?access_token=YOUR_TOKEN&ad_reached_countries=['JP']&search_terms=美容&limit=5"
```

### Step 5: VAAP に設定

**方法 1: API経由**
```bash
curl -X POST "http://localhost:8000/api/v1/settings/api-keys" \
  -H "Content-Type: application/json" \
  -d '{"meta_access_token": "YOUR_TOKEN"}'
```

**方法 2: DB直接**
```sql
UPDATE api_keys SET value = 'YOUR_TOKEN' WHERE key = 'meta_access_token';
-- or
INSERT INTO api_keys (key, value) VALUES ('meta_access_token', 'YOUR_TOKEN');
```

**方法 3: 環境変数**
```bash
export META_ACCESS_TOKEN="YOUR_TOKEN"
```

### Step 6: クロールテスト
```bash
# VAAP経由でクロール
curl -X POST "http://localhost:8000/api/v1/rankings/quick-crawl" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "美容", "limit": 10}'
```

---

## トークンの種類と有効期限

| 種類 | 有効期限 | 用途 |
|------|---------|------|
| 短期ユーザートークン | 1-2時間 | テスト用 |
| 長期ユーザートークン | 60日 | 開発・小規模運用 |
| ページトークン | 無期限 | ページ管理（広告閲覧には不向き） |
| システムユーザートークン | 無期限 | ビジネスマネージャー経由（推奨） |

### 推奨: システムユーザートークン（本番用）
1. ビジネスマネージャー → 設定 → システムユーザー
2. 新しいシステムユーザーを作成
3. アプリにアクセス権を付与
4. トークンを生成（無期限）

---

## Ad Library API の制約

### レートリミット
- 200 calls/hour（標準）
- 1リクエスト最大25件
- 1時間で最大 5000件の広告ID取得

### 取得できるデータ
```json
{
  "id": "12345678",
  "ad_creative_bodies": ["広告テキスト..."],
  "ad_creative_link_captions": ["リンクキャプション"],
  "ad_creative_link_titles": ["リンクタイトル"],
  "ad_delivery_start_time": "2025-01-15",
  "ad_delivery_stop_time": null,
  "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/...",
  "bylines": "株式会社XXX",
  "currency": "JPY",
  "demographic_distribution": [...],
  "delivery_by_region": [...],
  "estimated_audience_size": {"lower_bound": 10000, "upper_bound": 50000},
  "impressions": {"lower_bound": 1000, "upper_bound": 5000},
  "languages": ["ja"],
  "page_id": "98765",
  "page_name": "XXX公式",
  "publisher_platforms": ["facebook", "instagram"],
  "spend": {"lower_bound": 10000, "upper_bound": 50000}
}
```

### 取得できないデータ（別途推定が必要）
- 実際の再生数
- 実際の消化額
- クリック数/CTR
- CVR
- 動画URL（snapshot_url からスクレイピングで抽出）

---

## トークン管理の自動化

### token_manager.py（既存）
`backend/app/services/meta_marketing/token_manager.py`
- トークンの保存・取得
- 有効期限チェック
- 自動リフレッシュ（長期トークンの場合）

### 期限切れ検知
```python
# 定期的にトークン有効性をチェック
async def check_token_health():
    token = get_stored_token()
    try:
        r = await httpx.get(f"https://graph.facebook.com/v19.0/me?access_token={token}")
        if r.status_code == 200:
            return {"status": "valid", "expires_at": extract_expiry(r)}
        else:
            return {"status": "invalid", "error": r.json()}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### フロントでの通知
```typescript
// 設定画面にトークンステータス表示
// 期限切れ7日前にアラート
// 期限切れ時に赤バナー + 再設定リンク
```

---

## トラブルシューティング

### エラー: "Invalid OAuth access token"
→ トークンが期限切れ。再取得が必要。

### エラー: "Application does not have permission"
→ `ads_read` パーミッションが不足。Graph API Explorer で追加。

### エラー: "(#4) Application request limit reached"
→ レートリミット。1時間待つか、リクエスト頻度を下げる。

### エラー: "Ad archive search is not supported for this country"
→ `ad_reached_countries` パラメータを確認。`['JP']` を指定。

### クロール結果が0件
→ キーワードを変えてみる。英語ではなく日本語で。
→ 広告が配信停止している可能性。active_status フィルターを外す。
