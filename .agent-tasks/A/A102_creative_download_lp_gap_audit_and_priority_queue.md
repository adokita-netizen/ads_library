# A102: Creative / Download / LP Gap Audit & Priority Queue

## 優先度: 🅰️ A（クリティカル）

## 目的
- 「CRが正確に取れる / そのままDLできる / LP遷移先も取れる」を日次で監査し、復旧優先順位を自動で出せるようにする

## 対象ファイル
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/services/data_quality_report.py`
- `backend/scripts/check_ad_survival.py`

## 実装タスク
1. `creative_viewable_rate / creative_downloadable_rate / lp_present_rate / lp_resolved_rate` を日次KPI化
2. 広告ごとに `needs_cr_recovery / needs_download_recovery / needs_lp_resolution` を判定
3. `updated_at`, `platform`, `is_active`, `spend` を使って「復旧優先広告 Top N」を出す
4. planner や dashboard が使える JSON 形式で `creative_library_gap_audit` を返せるようにする
5. 失敗理由の集計キーを固定する
   - `missing_creative`
   - `not_downloadable`
   - `missing_lp`
   - `lp_unresolved`
   - `stale_snapshot`

## 完了条件
- [x] CR/DL/LP の欠損率を毎日追える
- [x] 復旧優先広告 Top N を自動算出できる
- [x] B/C/D の改善効果を数値で比較できる

## 制約
- Agent D が書く media recovery metadata は削除しない
- 監査・集計に寄せ、メディア抽出や UI 実装には踏み込まない
