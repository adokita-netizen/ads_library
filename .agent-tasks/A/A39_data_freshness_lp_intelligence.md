# A39: Data Freshness + LP Intelligence Precision Wave

## 概要
クロール完了後に「最新情報が見えている」ことをデータ面で担保する。
併せて、遷移先LPの情報取得精度を引き上げる。

## 背景
- quick-crawlは成功しても、検索結果や分析材料が不十分だと体感品質が落ちる
- LP情報（title/description/og:image/canonical 等）の欠損が分析精度に影響する
- 「最新データ反映」を定量監視できる仕組みが不足している

## タスク

### Task 1: クロール鮮度メタデータの標準化
- `ad_metadata` に以下を標準保存
  - `last_crawled_at`
  - `crawl_source` (`quick_crawl` / `scheduled_crawl`)
  - `freshness_ttl_sec`
  - `lp_snapshot_at`
- 保存フォーマットをUTC ISO8601で統一

### Task 2: LP情報取得スキーマ強化
- LP取得結果を `ad_metadata.lp_info` に統一格納
  - `final_url`
  - `http_status`
  - `title`
  - `description`
  - `canonical`
  - `og_image`
  - `lang`
  - `fetched_at`
- 欠損/失敗理由を `lp_fetch_error_code` に標準化
  - `timeout`, `dns_error`, `blocked`, `invalid_html`, `unknown`

### Task 3: 日次鮮度監査ジョブ
- 新規: `backend/scripts/audit_data_freshness.py`
- 出力:
  - 24時間以内更新率
  - LP情報欠損率
  - platform別鮮度偏差
  - stale広告トップN
- しきい値超過で警告ログ出力（後続通知はC担当と連携）

### Task 4: クロール結果と検索反映の整合監査
- quick-crawl後に増えた件数と、検索APIで見える件数の差分を監査
- 新規: `backend/scripts/audit_crawl_search_consistency.py`
- 監査結果をJSONで保存し、再現可能にする

## 完了条件
- [ ] ad_metadataの鮮度キーが新規/既存データで統一される
- [ ] LP情報が標準キーで保存され、失敗理由コードが付与される
- [ ] 日次鮮度監査レポートが生成できる
- [ ] crawl→search整合監査が自動実行できる

## 触っていいファイル
- `backend/scripts/audit_data_freshness.py` (新規)
- `backend/scripts/audit_crawl_search_consistency.py` (新規)
- `backend/scripts/check_lp_health.py` (拡張)
- `backend/app/models/ad.py` (キー追記のみ)
- `backend/app/tasks/metrics_tasks.py` (鮮度キー更新のみ)

## 連携
- C41のエラーレスポンス標準化とエラーコード辞書を合わせること

