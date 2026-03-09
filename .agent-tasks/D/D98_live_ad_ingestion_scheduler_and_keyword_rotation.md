# D98: Live Ad Ingestion Scheduler & Keyword Rotation

## 優先度: 🅰️ A（クリティカル）

## 目的
- 実広告が継続流入するよう、日次クロールとキーワードローテーションを安定運用する

## 対象ファイル
- `backend/app/tasks/crawl_tasks.py`
- `backend/app/services/crawling/meta_crawler.py`
- `backend/app/services/crawling/`
- `backend/scripts/`

## 実装タスク
1. 新着広告を優先する日次 crawl wave を固定する
2. `genre / platform / high-value keyword` のローテーション戦略を整備する
3. `最近入ってこないキーワード` を優先再クロール対象にする
4. 同一条件の重複 crawl を避けつつ、freshness を落とさないスケジューリングにする

## 完了条件
- [ ] 毎日新規広告が安定して流入する
- [ ] キーワード偏りと取りこぼしが減る
- [ ] 重複 crawl を増やさず新着を拾える
