# C43: Quick Crawl Contract + Quality Fix

## 目的
quick-crawlの仕様ギャップを埋め、取得品質のばらつきを減らす。
特に Meta 面は Facebook のみでなく Instagram を必須対象とする。

## タスク
1. `quick-crawl` の入力契約を見直し（platforms/country/limit）
 - デフォルト platforms を `["facebook","instagram"]` に変更
 - UIの媒体選択が未指定でも Meta2面を検索対象にする
2. 取得後フィルタで落ちる条件（言語・重複・品質）を監査
3. `error_code` と `failure_reason` の返却整合を統一
4. 取得件数・保存件数・検索可視件数の差分APIを固定

## 完了条件
- [x] quick-crawl仕様がUI要件と一致
- [x] Instagram広告が quick-crawl で取得対象になる
- [x] GLP-1系クエリの欠損要因が再現可能に説明できる
- [x] API契約テストが追加される

## 対象
- `backend/app/api/endpoints/rankings.py`
- `backend/tests/test_api.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

