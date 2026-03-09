# D96: Creative Library Recovery & Download Completeness

## 優先度: 🅰️ A（クリティカル）

## 問題
- UI導線を整えても、素材自体が不足している広告は「見れない・DLできない」
- `thumbnail はあるが image/video が無い`, `snapshot はあるが保存素材が無い` などの半端状態を減らす必要がある
- DL成功率を上げるには、取得優先順位と再回収フローを明示して実装する必要がある

## 対象ファイル
- `backend/app/services/media_extraction.py`
- `backend/app/tasks/media_tasks.py`
- `backend/scripts/backfill_media_urls.py`
- `backend/scripts/update_media_status.py`

## 実装方針

### 1. 復旧優先順位を固定
1. 既存S3キー確認
2. local cache確認
3. original image/video URL 再取得
4. snapshot から on-demand extract
5. browser fallback

### 2. 完全性スコアを上げる
- `viewable only`
- `downloadable`
- `downloadable + lp`
を分類し、`downloadable` 未満を重点復旧対象にする

### 3. 状態更新を明示
- `media_extraction_status`
- `media_completeness_score`
- `media_quality_issues`
- `last_recovery_attempt_at`

### 4. リカバリーバッチ
- `downloadable = false` の広告を一定件数ずつ再処理
- 成功時は最終取得元を残す
- 失敗時は理由を標準コードで残す

## 完了条件
- [ ] `downloadable = false` の広告数を継続的に減らせる
- [ ] snapshot only 状態からの復旧フローがある
- [ ] 再回収結果が status/metadata に残る
- [ ] UIが参照できる素材完全性の基礎データが揃う

## 制約
- Agent A/C 所有の指標計算やAPI契約を壊さない
- 重い browser fallback は通常経路失敗時のみ実行する
