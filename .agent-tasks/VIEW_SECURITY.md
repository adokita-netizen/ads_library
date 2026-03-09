# セキュリティ視点 — 本番公開前に潰すべきリスク

## Critical（公開前に必須）

### SEC-1: CORS wildcard
**場所**: `backend/app/main.py`
**現状**: `allow_origins=["*"]`
**リスク**: 任意のドメインからAPI呼び出し可能。データ漏洩、CSRF攻撃
**修正**:
```python
origins = [
    "https://d3qlbagx7gq5sp.cloudfront.net",
    "http://localhost:3000",  # dev only
]
app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
```

### SEC-2: APIキーの保存方法
**場所**: `backend/app/api/endpoints/settings.py`
**確認項目**:
- Meta API Token はDB平文？ → 暗号化必要
- OpenAI API Key はDB平文？ → 暗号化 or 環境変数
- Anthropic API Key はDB平文？ → 同上
**対策**: AWS Secrets Manager or KMS で暗号化

### SEC-3: 認証バイパスの可能性
**場所**: `backend/app/api/endpoints/` 全ルーター
**確認**: 全エンドポイントに認証ミドルウェアが掛かっているか
**特に危険**:
- `/rankings/export/csv` — データ全件ダウンロード
- `/settings/api-keys` — APIキー取得
- DELETE系エンドポイント
**対策**: JWT認証ミドルウェアの適用確認

### SEC-4: SQLインジェクション
**場所**: `backend/app/api/endpoints/rankings.py`
**リスク**: 14,779行のうち、生SQL or f-string クエリがないか
**確認**: `text(`, `f"SELECT`, `.execute(f"` のパターン検索
**対策**: SQLAlchemy ORM or パラメータバインディング徹底

---

## High（早めに対処）

### SEC-5: Rate Limiting 未設定
**現状**: API に rate limit がない（推定）
**リスク**: DDoS、スクレイピング、APIキー総当たり
**対策**:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
# 一般API: 100 req/min
# export: 10 req/min
# crawl: 5 req/min
```

### SEC-6: メディアプロキシの Open Redirect
**場所**: `backend/app/api/endpoints/media.py`
**リスク**: `/api/v1/media/thumbnail/{ad_id}` が外部URLにリダイレクト
- 攻撃者が任意URLを ads テーブルに入れると、プロキシ経由でアクセス
**対策**: 許可ドメインのホワイトリスト

### SEC-7: ファイルパス操作
**場所**: `backend/data/collections.json`, `saved_searches.json`
**リスク**: JSONファイルへの直接書き込み → パス操作の可能性
**対策**: DB移行、またはファイル名のサニタイズ

### SEC-8: Lambda 環境変数の露出
**確認**: Lambda の環境変数に DATABASE_URL (パスワード含む) が平文
**対策**: Secrets Manager 参照に変更

---

## Medium（時間があるとき）

### SEC-9: エラーメッセージにスタック情報
**リスク**: 500エラー時にPythonトレースバックが返る
**対策**: 本番では `debug=False`、一般的なエラーメッセージのみ返す

### SEC-10: 外部ライブラリの脆弱性
**対策**: `pip audit` or `safety check` で定期チェック

### SEC-11: CloudFront のキャッシュ設定
**確認**: API レスポンスがキャッシュされていないか
- 特に `/api/v1/settings/api-keys` がキャッシュされると致命的
**対策**: API パスに `Cache-Control: no-store` ヘッダー

### SEC-12: S3 バケットのアクセス権限
**確認**: メディア保存用S3がパブリックでないか
**対策**: CloudFront OAI/OAC 経由のみアクセス許可

---

## チェック実行方法

```bash
# SQL injection パターン検索
cd C:/Users/ishit/ads_library/backend
grep -rn "text(" app/api/ | grep -v ".pyc"
grep -rn 'f"SELECT' app/ | grep -v ".pyc"
grep -rn 'f"INSERT' app/ | grep -v ".pyc"
grep -rn 'f"UPDATE' app/ | grep -v ".pyc"
grep -rn 'f"DELETE' app/ | grep -v ".pyc"

# 認証なしエンドポイント検索
grep -rn "@router\." app/api/endpoints/ | grep -v "Depends" | head -30

# ハードコードされた認証情報
grep -rn "password" app/ | grep -v ".pyc" | grep -v "test"
grep -rn "secret" app/ | grep -v ".pyc" | grep -v "test"
grep -rn "api_key.*=" app/ | grep -v ".pyc"
```
