# エージェントC: メディアURL一括補完（バックエンド）

## 概要
多くの広告が `image_url` や `video_url` がNULLのまま。
フロントエンドのCreativeViewerが動作するには、これらのURLが必要。
既存データから可能な限りURLを補完する。

## プロジェクト情報
- パス: `C:\Users\ishit\ads_library`
- バックエンド: `backend/` (FastAPI + SQLAlchemy)
- DB: `backend/vaap_local.db` (SQLite)
- Adモデル: `backend/app/models/ad.py` (`ad_metadata` 属性 → DBカラム名 `metadata`)

## ブランチ名
`fix/media-url-backfill`

## 対象ファイル
- `backend/scripts/backfill_media_urls.py` (新規作成)
- `backend/app/tasks/crawl_tasks.py` (`_inline_enrich` の改善 — 任意)

## 手順

### 1. 現状調査
```python
import sys; sys.path.insert(0, ".")
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import func

session = SyncSessionLocal()
total = session.query(func.count(Ad.id)).scalar()
no_image = session.query(func.count(Ad.id)).filter(Ad.image_url.is_(None)).scalar()
no_video = session.query(func.count(Ad.id)).filter(Ad.video_url.is_(None)).scalar()
has_snapshot = session.query(func.count(Ad.id)).filter(Ad.snapshot_url.isnot(None)).scalar()
has_thumb = session.query(func.count(Ad.id)).filter(Ad.thumbnail_url.isnot(None)).scalar()
print(f"Total: {total}")
print(f"No image_url: {no_image}/{total}")
print(f"No video_url: {no_video}/{total}")
print(f"Has snapshot_url: {has_snapshot}/{total}")
print(f"Has thumbnail_url: {has_thumb}/{total}")
session.close()
```

### 2. スクリプト作成 (`backend/scripts/backfill_media_urls.py`)

処理ロジック（優先順位）:

#### Phase 1: thumbnail_url からのコピー（即座にできる）
```python
# image_url が NULL で thumbnail_url がある場合、コピー
if not ad.image_url and ad.thumbnail_url:
    ad.image_url = ad.thumbnail_url
```

#### Phase 2: snapshot_url からの抽出（MediaExtractor使用）
```python
from app.services.media_extraction import MediaExtractor
import asyncio

extractor = MediaExtractor()

# snapshot_url がある広告を対象
ads_with_snapshot = session.query(Ad).filter(
    Ad.snapshot_url.isnot(None),
    Ad.image_url.is_(None),  # まだimage_urlがないもの
).all()

for ad in ads_with_snapshot:
    try:
        # asyncをsyncで実行
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            extractor.extract(ad.snapshot_url, use_playwright=False)
        )
        loop.close()

        if result.image_urls:
            ad.image_url = result.image_urls[0]
        if result.video_urls and not ad.video_url:
            ad.video_url = result.video_urls[0]
        if result.creative_type and result.creative_type != "unknown":
            ad.creative_type = result.creative_type
    except Exception as e:
        print(f"  Failed for Ad {ad.id}: {e}")

    time.sleep(1.5)  # レート制限
```

#### Phase 3: ad_metadata からの追加抽出
```python
# ad_metadata にメディア情報が含まれている場合がある
meta = ad.ad_metadata or {}
if not ad.video_url:
    # render_ad の結果にビデオURLが含まれている場合
    video_url = meta.get("video_url") or meta.get("og_video")
    if video_url and video_url.startswith("http"):
        ad.video_url = video_url
```

### 3. バッチ処理
```python
BATCH_SIZE = 10
for i, ad in enumerate(ads):
    # ... 処理 ...
    if (i + 1) % BATCH_SIZE == 0:
        session.commit()
        print(f"  Progress: {i+1}/{len(ads)}")
        time.sleep(1.5)
session.commit()
```

### 4. crawl_tasks.py の改善（任意）
`backend/app/tasks/crawl_tasks.py` の `_inline_enrich` 関数を確認し、
今後のクロールで自動的に image_url/video_url が埋まるようにする:

- render_ad HTML から `<video src="...">` を抽出
- `<video poster="...">` を thumbnail として使用
- `<img>` で最大サイズの画像を image_url に設定

### 5. 検証
```python
no_image_after = session.query(func.count(Ad.id)).filter(Ad.image_url.is_(None)).scalar()
print(f"image_url NULL: {no_image} -> {no_image_after}")
```

目標: image_url がNULLの件数を大幅削減（0件が理想）

## 注意事項
- `SyncSessionLocal` を使用
- `flag_modified(ad, "ad_metadata")` でJSON変更を検知させる
- MediaExtractorの `use_playwright=False` で軽量HTTP抽出を先に試す
- snapshot_url が render_ad 形式（access_token含む）の場合、トークンが有効か確認
- レート制限: 各リクエスト間に1.5秒のディレイ
- `backend/` ディレクトリから実行: `cd C:/Users/ishit/ads_library/backend && python scripts/backfill_media_urls.py`

---

## 実行ログ

### 2026-02-28 セッション1 — 実装完了
- `backend/scripts/backfill_media_urls.py` を新規作成
- `backend/app/tasks/crawl_tasks.py` の `_inline_enrich` を改善
  - `<video src>` と `<video><source src>` からの `video_url` 抽出を追加

### 2026-02-28 セッション2 — 実行・検証完了
- **ステータス: DONE (補完不要と判明)**

#### 実行前の調査結果
| 項目 | 件数 | 備考 |
|------|------|------|
| Total ads | 176 | |
| image_url NULL | 0 | 既に全件補完済み |
| video_url NULL | 88 | 内訳: image=73, unknown=15 |
| snapshot_url パターン | render_ad=29, ads/library=147 | |

#### スクリプト実行結果
- **Phase 1**: 候補0件（image_url全件済み）
- **Phase 2**: render_ad 11件を試行 → 全件 **400 Bad Request**（アクセストークン期限切れ）
- **Phase 3**: ad_metadata にvideo系キーなし → 0件

#### 結論
- video_url NULLの88件中73件は **image広告（正常にNULL）**
- 残り15件は unknown型 → アクセストークン更新後に再実行で判定可能
- **image_url の補完は完了済み。video_url はトークン更新が前提条件**

#### スクリプト修正履歴
1. Phase 2 フィルタを `AND` → `OR` に修正（image_url全件済みでも動作するように）
2. Phase 2 対象を `render_ad` URL のみに絞り込み（ads/library は Facebook 403のため）

#### 次のアクション
- [ ] Meta アクセストークンを更新（Settings画面から）
- [ ] トークン更新後に `cd backend && python scripts/backfill_media_urls.py` を再実行
- [ ] unknown 15件の creative_type 判定を確認
