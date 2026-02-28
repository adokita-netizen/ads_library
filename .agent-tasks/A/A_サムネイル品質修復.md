# エージェントA: サムネイル品質修復

## 概要
176件中14件のサムネイルが低品質（10件がFacebookプロフィール画像 s200x200、4件がGoogle Favicon）。
これらを高解像度のクリエイティブ画像に差し替える。

## プロジェクト情報
- パス: `C:\Users\ishit\ads_library`
- バックエンド: `backend/` (FastAPI + SQLAlchemy)
- DB: `backend/vaap_local.db` (SQLite)
- Adモデル: `backend/app/models/ad.py` (`ad_metadata` 属性 → DBカラム名 `metadata`)

## ブランチ名
`fix/thumbnail-quality`

## 対象ファイル
- `backend/scripts/fix_bad_thumbnails.py` (新規作成)
- `backend/app/services/thumbnail_fetcher.py` (必要に応じて修正)

## 手順

### 1. 現状確認
以下のSQLで対象を確認:
```python
# backend/ ディレクトリで実行
import sys; sys.path.insert(0, ".")
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import or_

session = SyncSessionLocal()
bad_ads = session.query(Ad).filter(
    or_(
        Ad.thumbnail_url.like("%s200x200%"),
        Ad.thumbnail_url.like("%favicons%"),
    )
).all()
print(f"対象: {len(bad_ads)}件")
for ad in bad_ads:
    print(f"  Ad {ad.id}: ext_id={ad.external_id}, thumb={ad.thumbnail_url[:60]}")
session.close()
```

### 2. スクリプト作成 (`backend/scripts/fix_bad_thumbnails.py`)
以下の優先順位で代替サムネイルを取得:

1. **render_ad エンドポイント**: `https://www.facebook.com/ads/archive/render_ad/?id={external_id}&access_token={token}`
   - HTMLをパースし、`<img>` タグの `src` が `scontent` や `fbcdn` を含むものを探す
   - サイズが大きいもの（width > 100）を優先
2. **destination_url の og:image**: 広告の遷移先LPからOpen Graphタグ取得
   - `httpx` で `destination_url` をフェッチ → BeautifulSoup で `<meta property="og:image">` を抽出
3. **thumbnail_url をそのまま残す**: 上記全て失敗時は現状維持

アクセストークンの取得:
```python
from app.api.endpoints.settings import load_api_keys_from_db
keys = load_api_keys_from_db()
meta_keys = keys.get("meta", keys.get("facebook", {}))
token = meta_keys.get("access_token")
```

### 3. DB更新
```python
from sqlalchemy.orm.attributes import flag_modified

ad.thumbnail_url = new_url
ad.image_url = ad.image_url or new_url
meta = dict(ad.ad_metadata or {})
meta["thumbnail_fixed"] = True
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()
```

### 4. 検証
```python
count = session.query(Ad).filter(
    or_(
        Ad.thumbnail_url.like("%s200x200%"),
        Ad.thumbnail_url.like("%favicons%"),
    )
).count()
print(f"残り低品質サムネイル: {count}件")  # 目標: 0
```

## 注意事項
- `SyncSessionLocal` を使用（asyncではない）
- レート制限: 各リクエスト間に1秒のディレイ
- render_ad が空HTMLを返す場合がある（`広告ライブラリ` のみのテキスト）→ スキップしてog:imageへ
- Facebook CDN URLのパターン: `scontent-*.fbcdn.net` or `*.fna.fbcdn.net`
