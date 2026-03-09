# C42: API Error Crush + Capacity Guard

## 概要
`quick-crawl` と検索APIのエラーを潰し、件数不足時でも落ちないAPI基盤へ引き上げる。
500発生時の原因追跡を即時可能にする。

## 目的
- `quick-crawl` 500/timeoutを最小化
- 検索APIで最新が見えない不整合を検知・返却
- エラーをコード化し、UI/運用が同じ意味で扱える状態にする

## タスク

### Task 1: quick-crawl保護強化
- タイムアウト・例外を分類して `error_code` 返却
  - `crawl_timeout`
  - `crawler_upstream_error`
  - `db_write_error`
  - `unknown`
- `job_id` 単位で失敗理由を必ず保存

### Task 2: 件数不足時のフェイルソフト
- `new_ads_count` が閾値未満のとき補助処理を発動
  - 追加クエリ投入 or 既存候補再評価
- APIレスポンスに `recovery_action` を含める

### Task 3: consistency APIの実運用化
- `GET /rankings/quick-crawl/{job_id}/consistency` を必須運用
- `db_inserted_count` と `search_visible_count` の差分が閾値超過なら警告
- UIが扱える `is_consistent` を返す

### Task 4: 契約テスト追加
- `backend/tests/test_api.py` に追加
  - quick-crawl success/timeout/db-write-failure
  - consistency API
  - error_code契約

## 完了条件
- [x] quick-crawl 500の主因がerror_codeで判別できる
- [x] 件数不足時の補助動作がレスポンスで観測できる
- [x] crawl→search整合がAPIで判定できる
- [x] 契約テストが追加され通過する

## 触っていいファイル
- `backend/app/api/endpoints/rankings.py`
- `backend/tests/test_api.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 連携
- A40の監査CLIで使うエラーコードと一致させる
- B46のUI文言マップ更新を前提に共有する


