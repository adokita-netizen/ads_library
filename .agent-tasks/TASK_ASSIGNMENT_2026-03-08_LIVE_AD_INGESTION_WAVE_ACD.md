# TASK ASSIGNMENT: 2026-03-08 Live Ad Ingestion Wave (ACD)

## 目的
- 実際の広告が毎日どんどん入ってきて、しかも重複や低品質を抑えながら使える状態まで持っていく

## Agent A
- `A105_live_ad_ingestion_freshness_audit.md`
- 役割:
  - 流入量/鮮度/重複率の監査
  - 停止キーワードや偏りの検知

## Agent C
- `C103_ingestion_quality_gate_and_dedup_contract.md`
- 役割:
  - ingest 品質ゲートの固定
  - dedup reason code と結果語彙の統一

## Agent D
- `D98_live_ad_ingestion_scheduler_and_keyword_rotation.md`
- `D99_live_ad_ingestion_reliability_and_backfill_wave.md`
- 役割:
  - 日次新着クロール
  - キーワードローテーション
  - 失敗時の再試行/backfill

## 実行順
1. C103
2. D98
3. D99
4. A105
