# D106: Meta API-First Pipeline Hardening

## 優先度
- `P0`

## 目的
- Meta crawler を API 主経路に固定し、detail enrich・creative・LP の回収安定性を上げる

## 対象
- `backend/app/services/crawling/meta_crawler.py`
- `backend/app/tasks/crawl_tasks.py`
- `backend/scripts/`
- `backend/tests/`

## 実装タスク
1. access token が有効なときは browser fallback に落ちる前に API 失敗理由を明確化する
2. `Execution context was destroyed` を再試行・再ナビゲーションでさらに潰す
3. ad detail enrich 失敗時に `metric_source / creative_source / lp_source` を欠損理由つきで残す
4. thumbnail/video/LP 補完の fallback を Meta 向けに整理する
5. Meta API 取得成功ケースの回帰テストを追加する

## 完了条件
- [ ] Meta API 主経路が安定する
- [ ] detail enrich 失敗率が下がる
- [ ] creative / LP / metrics 欠損理由が残る
