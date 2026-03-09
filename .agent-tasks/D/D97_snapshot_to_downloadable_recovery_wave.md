# D97: Snapshot to Downloadable Recovery Wave

## 優先度: 🅰️ A（クリティカル）

## 目的
- snapshot はあるが downloadable でない広告を減らし、CRをそのままDL可能にする

## 対象ファイル
- `backend/app/services/media_extraction.py`
- `backend/app/tasks/media_tasks.py`
- `backend/scripts/update_media_status.py`
- `backend/scripts/aggressive_media_recovery.py`

## 実装タスク
1. `snapshot_url only` 広告の抽出優先バッチを作る
2. poster / og:image / iframe / browser fallback の成功率を計測
3. `downloadable=false` の広告を優先再処理
4. `creative_fetch_reason` と `media_completeness_score` を更新

## 完了条件
- [ ] snapshot only 広告の downloadable 化が進む
- [ ] recovery 成功率を計測できる
- [ ] failed reason が標準コードで残る

