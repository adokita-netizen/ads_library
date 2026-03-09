# C103: Ingestion Quality Gate & Dedup Contract

## 優先度: 🅰️ A（クリティカル）

## 目的
- 広告がどんどん入ってきてもゴミデータや重複が増えすぎないよう、取り込み契約と品質ゲートを固定する

## 対象ファイル
- `backend/app/api/endpoints/ads.py`
- `backend/app/models/ad.py`
- `backend/app/schemas/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `external_id / snapshot_url / advertiser_name / platform` の最低品質ゲートを定義
2. `new / updated / duplicate / rejected` の取り込み結果語彙を固定
3. 重複判定の優先キーを契約化する
   - `platform + external_id`
   - `snapshot_url`
   - `title + advertiser + started_date`
4. ingest 系レスポンスや運用出力の reason code を固定する
   - `missing_external_id`
   - `missing_snapshot_url`
   - `duplicate_external_id`
   - `duplicate_snapshot`
   - `low_quality_payload`

## 完了条件
- [ ] 取り込み品質ゲートが明文化される
- [ ] 重複/拒否の語彙が固定される
- [ ] A/D が共通前提で監査・運用できる
