# D25: メディアパイプライン最適化

## 目的
サムネイルとメディアの表示品質を向上。

## タスク

### 1. サムネイル品質チェック
- `backend/scripts/check_thumbnail_quality.py` を作成
- 全広告のサムネイルURLの有効性チェック
- 404/403エラーのURLをリスト化
- 代替URLの検索

### 2. メディアキャッシュ最適化
- `backend/scripts/optimize_media_cache.py` を改善
- 頻繁にアクセスされるメディアのプリキャッシュ
- 不要なキャッシュの削除

### 3. サムネイルプレースホルダー生成
- `backend/scripts/generate_placeholder_thumbnails.py` を作成
- サムネイルがない広告用のプレースホルダー画像生成
- ジャンル別のデフォルトアイコン

## 制約
- rankings.pyは編集禁止
- scripts/ と services/ のみ
