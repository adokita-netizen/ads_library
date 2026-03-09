# A101: Creative Library Coverage Audit & Recovery KPI

## 優先度: 🅱️ B（重要）

## 問題
- 広告ライブラリを「見れる・DLできる」状態にするには、媒体ごとの欠損率を継続監査する必要がある
- 現状は `クリエイティブ閲覧可否 / DL可否 / LP有無` を日次で俯瞰する基盤が弱い
- D/C/B が進めた改善が、実データ上でどこまで効いたかを A 側で追える状態にしたい

## 対象ファイル
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/services/data_quality_report.py`
- `backend/scripts/check_ad_survival.py`

## 実装方針

### 1. 日次KPIを定義
- `creative_viewable_rate`
- `creative_downloadable_rate`
- `lp_present_rate`
- `missing_media_count`
- `missing_lp_count`
- `platform_breakdown`
- `genre_breakdown`

### 2. 広告単位の監査判定を固定
以下の真偽判定を日次で作る:

```python
has_viewable_creative = bool(thumbnail_url or image_url or video_url or thumbnail_s3_key or image_s3_key or s3_key)
has_downloadable_creative = bool(image_s3_key or s3_key or local_cached_file)
has_lp = bool(destination_url)
```

### 3. レポート出力
- 全体サマリ
- 媒体別の欠損数
- ジャンル別の欠損数
- `updated_at` 降順の「優先復旧対象 Top N」

### 4. Planner/Dashboard に渡す形式を固定
- JSON で `creative_library_audit` を返せる形にする
- 失敗理由は集計キーを揃える
  - `missing_media`
  - `missing_lp`
  - `stale_creative`
  - `download_unavailable`

## 完了条件
- [x] 日次で Creative Library 監査KPIを算出できる
- [x] 媒体別/ジャンル別の欠損数が見える
- [x] 復旧優先広告 Top N を抽出できる
- [x] D/C/B の改善後に数値差分を追跡できる

## 制約
- Agent D 所有の `ad_metadata` メディアキーは上書きしない
- 監査・集計中心とし、メディア抽出処理そのものは触らない
