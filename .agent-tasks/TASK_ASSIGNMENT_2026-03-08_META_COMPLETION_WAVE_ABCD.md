# TASK ASSIGNMENT: 2026-03-08 Meta Completion Wave (ABCD)

## 目的
- Meta だけで `日本語広告 -> 実データ -> クリエイティブ -> LP -> 新着継続取得` を実運用レベルまで引き上げる
- 既に通った `long-lived token + ads_archive` を前提に、残る不安定点を集中的に潰す
- browser fallback 依存を減らし、Meta API を主経路にした完成度 90% 以上を目指す

## 現状
- Meta token は長期トークン化済みで、`ads_archive` 200 応答を確認済み
- `run_live_ad_ingestion_wave.py --inline --keyword-limit 1 --limit-per-platform 3` で `saved_count=3`
- 一方で detail enrich では `Execution context was destroyed` が残る
- thumbnail/video/LP の補完は通るが、安定性と provenance 表示がまだ弱い
- scheduler / duplicate / freshness の Meta 専用運用が未完成

## この wave で固定したいこと
- Meta API が通る限り browser fallback に落ちない
- `real / estimated / missing` の区別が API / UI / 監査で一貫する
- Meta 新着の継続取得が `keyword rotation + freshness + scheduler` で回る
- creative / LP / metrics の欠損理由が追える

## Agent A
- `A109_meta_completion_audit_and_acceptance.md`
- 役割:
  - Meta 完成度の監査と受け入れ基準の固定
  - 実数値 / 推定値 / 欠損の混在監査
  - 日本語広告精度と新着率の計測

## Agent B
- `B101_meta_quality_and_provenance_ui.md`
- 役割:
  - Meta 広告の `real / estimated / missing` と media / LP 状態の UI 表示
  - 新着 Meta 広告の監視導線
  - fallback 由来データの provenance 表示

## Agent C
- `C117_meta_data_contract_and_freshness_api.md`
- `C118_meta_token_runtime_and_health_contract.md`
- 役割:
  - Meta 用 freshness / provenance / quality 状態の API 契約固定
  - token health / expiry / source / last_success の運用 API 固定

## Agent D
- `D106_meta_api_first_pipeline_hardening.md`
- `D107_meta_scheduler_and_backfill_completion.md`
- 役割:
  - Meta API 主経路化、detail enrich 安定化、creative/LP 補完強化
  - Meta 専用 scheduler / duplicate policy / backfill completion

## 実行順
1. C117
2. D106
3. C118
4. D107
5. A109
6. B101

## 受け渡しルール
- D -> C/A/B:
  - `metric_source`
  - `creative_source`
  - `lp_source`
  - `token_source`
  - `last_meta_success_at`
  - `meta_quality_state`
- C -> B:
  - UI で出す enum / badge / freshness / provenance label
- A -> D/C:
  - 欠損パターン
  - 推定値の誤用パターン
  - 新着率改善に効く監査観点

## 成功条件
- Meta だけなら `日本語広告の継続取得` が安定して回る
- 実数値と推定値が明確に区別され、誤認しにくい
- creative / LP / metrics 欠損時の理由と recovery 導線が追える
