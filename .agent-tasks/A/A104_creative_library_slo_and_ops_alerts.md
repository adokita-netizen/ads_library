# A104: Creative Library SLO & Ops Alerts

## 優先度: 🅰️ A（クリティカル）

## 目的
- CR/DL/LP の品質低下を放置しないため、運用SLOとアラート基準を固定する

## 対象ファイル
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/services/data_quality_report.py`
- `backend/scripts/check_ad_survival.py`

## 実装タスク
1. `creative_viewable_rate / creative_downloadable_rate / lp_resolved_rate` の SLO しきい値を定義
2. 前日比悪化、媒体別急落、特定 advertiser 偏りを検知する
3. `warning / critical` の判定を JSON 出力に含める
4. planner や通知基盤が使える `ops_alert_candidates` を出す

## 完了条件
- [x] Creative Library 品質の悪化を自動検知できる
- [x] 監査レポートから運用アクションへ繋げられる
