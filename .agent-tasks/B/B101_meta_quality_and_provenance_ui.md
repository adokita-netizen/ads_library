# B101: Meta Quality and Provenance UI

## 優先度
- `P0`

## 目的
- Meta 広告の品質状態を UI で誤認なく見せ、実数値・推定値・欠損を即判別できるようにする

## 対象
- `frontend/src/components/`
- `frontend/src/types/`
- `frontend/e2e/`

## 実装タスク
1. Meta 広告に `実数値 / 推定 / 欠損` badge を追加する
2. `creative_source / lp_source / metric_source / token_source` の provenance 表示を追加する
3. 新着 Meta 広告に `new` と `last_meta_success_at` を出す
4. `snapshot only / creative pending / lp missing / detail enrich failed` を empty state として整理する
5. Meta 限定の QA E2E を追加して、誤表示を防ぐ

## 完了条件
- [ ] Meta の品質状態が UI で明確に見える
- [ ] 実数値と推定値を見間違えにくい
- [ ] fallback 由来のデータが provenance で追える
