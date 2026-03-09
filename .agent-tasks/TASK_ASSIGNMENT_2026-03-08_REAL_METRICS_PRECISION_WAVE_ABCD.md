# TASK ASSIGNMENT: 2026-03-08 Real Metrics Precision Wave (ABCD)

## 目的
- 「見た目だけ数値がある」状態をやめ、実データ由来の数値がどこまで入っているかを明確にする
- hit_score / spend / impressions / reach / LP score / media quality の精度を、実測値優先で改善する
- frontend / API / task / dataops の全レイヤで `real vs estimated vs missing` を区別できるようにする

## 最終ゴール
- 広告詳細・一覧・分析画面で、実データ数値が入っている項目は provenance 付きで表示される
- 実データ未取得時は推定値か欠損かが明示される
- ingestion 後に自動で backfill / audit / contract test が回り、数値品質の劣化を検知できる

## Agent A
- `A106_real_metrics_coverage_and_numeric_truth_audit.md`
- 役割:
  - 実数値カバレッジ監査
  - 実測/推定/欠損の比率集計
  - 日次 quality report と改善優先順位付け

## Agent B
- `B98_real_metrics_provenance_and_numeric_ui.md`
- 役割:
  - 数値 provenance UI
  - 実測/推定/欠損の視覚的区別
  - 数値が空や stale の時の empty state / warning

## Agent C
- `C112_real_metrics_contract_and_provenance_api.md`
- 役割:
  - 数値フィールド契約の固定
  - provenance / freshness / confidence の API 標準化
  - contract test / fixture / error code 整備

## Agent D
- `D100_real_metrics_ingestion_pipeline.md`
- `D101_real_metrics_backfill_and_scheduler.md`
- 役割:
  - 実データ源からの数値取り込み強化
  - stale ads の backfill
  - 定期実行と失敗再試行

## 実行順
1. C112
2. D100
3. D101
4. A106
5. B98

## 受け渡しルール
- D → A/C:
  - 実データ数値ソースの field mapping
  - source ごとの freshness と failure reason
- C → B:
  - UI が使う固定 response shape
  - `metric_source`, `metric_status`, `freshness_status`, `confidence_label`
- A → B/C/D:
  - coverage gap 上位項目
  - 「実数値を優先して埋めるべき」媒体 / ジャンル / source
