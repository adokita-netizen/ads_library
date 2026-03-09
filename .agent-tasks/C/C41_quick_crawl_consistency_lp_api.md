# C41: Quick Crawl Consistency + LP Info API Precision Wave

## 概要
quick-crawl成功後に最新情報がAPIで一貫して返る状態を固定し、
LP情報取得を「取得結果が見えるAPI」として整備する。

## 背景
- 500/タイムアウトや反映遅延が起きると、UI側で成功表示でも信頼を失う
- LP情報取得の成否や鮮度がAPIで十分に観測できない
- エラー理由の標準化不足でデバッグコストが高い

## タスク

### Task 1: quick-crawlレスポンス契約の固定
- `POST /rankings/quick-crawl` の返却を標準化
  - `status`
  - `job_id`
  - `new_ads_count`
  - `total_ads_found`
  - `keywords_searched`
  - `completed_at`
  - `error_code`（失敗時）
- 成功/失敗のJSON形式を統一し、HTTPコードを一貫化

### Task 2: crawl→search整合確認APIの追加
- 新規: `GET /rankings/quick-crawl/{job_id}/consistency`
- 返却:
  - `db_inserted_count`
  - `search_visible_count`
  - `delta`
  - `checked_at`
  - `is_consistent`
- UIが「反映待ち」か「不整合」か判定できるようにする

### Task 3: LP情報可視化APIの追加/拡張
- 新規または拡張:
  - `GET /rankings/lp-info/{ad_id}`
  - `POST /rankings/lp-info/refresh`
- 返却項目:
  - `fetch_status`
  - `error_code`
  - `title`, `description`, `canonical`, `og_image`
  - `final_url`, `http_status`
  - `fetched_at`

### Task 4: API契約テストとエラーコード辞書
- pytestで契約テスト追加
  - quick-crawl成功/失敗
  - consistency API
  - lp-info 取得/失敗
- エラーコード辞書を `.agent-tasks/API_CONTRACT_REGISTRY.md` に追記

## 完了条件
- [x] quick-crawlの成功/失敗契約が固定化される
- [x] crawl→search整合をjob_id単位で確認できる
- [x] LP情報の取得結果をAPIで観測できる
- [x] 契約テストが追加され、主要ケースが通る

## 触っていいファイル
- `backend/app/api/endpoints/rankings.py`
- `backend/tests/test_api.py`
- `backend/tests/test_rankings_dpro_parity.py`（必要時）
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 連携
- A39の鮮度メタデータキーと一致させること
- B45へ返却フィールド確定版を共有すること


