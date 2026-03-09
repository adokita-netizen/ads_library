# A40: Ads Volume Recovery + Error Zero (Data Layer)

## 概要
広告母数を増やしつつ、データ層で発生するエラーを潰し切る。
「収集できたが保存で落ちる」「保存できたが欠損だらけ」を同時に解消する。

## 目的
- 日次で十分な件数を確保（最低ラインを下回らない）
- DB保存時エラーをゼロ化（再試行で回復可能にする）
- 欠損データ率を下げ、フロント表示エラーの発火源を減らす

## タスク

### Task 1: 広告件数KPIの下限ガード
- `top30` だけでなく `target_min_ads_per_day` を設定（例: 100）
- 未達時は補助キーワード・補助媒体を自動投入して再収集
- 収集実績を日次レポートに保存（成功数/失敗数/未達理由）

### Task 2: 保存処理エラーの再試行統一
- DB書き込み失敗時の再試行（指数バックオフ）を全バッチで統一
- 一時失敗/恒久失敗を分離し、恒久失敗はDLQ相当へ退避
- 失敗広告IDを再処理キューに積む

### Task 3: 必須フィールド補完の強制
- `title`, `platform`, `advertiser_name`, `destination_url` の欠損を検知
- 補完不能レコードは `incomplete_reason` を付けて隔離
- 一覧APIに流さない（UIエラー予防）

### Task 4: 日次ヘルスチェックCLI
- 新規: `backend/scripts/audit_ads_volume_errors.py`
- 出力:
  - 収集件数（前日/7日平均）
  - 保存失敗件数
  - 欠損フィールド率
  - 再処理待ち件数

## 完了条件
- [ ] 日次広告件数が最低ラインを継続達成
- [ ] 保存系の未処理エラーが0件（または再試行キューで吸収）
- [ ] 必須欠損レコードが一覧流入しない
- [ ] 監査CLIで件数/失敗を可視化できる

## 触っていいファイル
- `backend/scripts/audit_ads_volume_errors.py` (新規)
- `backend/scripts/collect_real_metrics.py`
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/core/database.py`

## 連携
- C42のAPIエラー分類とエラーコードを一致させる

