# D107: Meta Scheduler and Backfill Completion

## 優先度
- `P0`

## 目的
- Meta 新着取得を継続運転に寄せ、取り逃し広告の backfill まで回るようにする

## 対象
- `backend/scripts/run_live_ad_ingestion_wave.py`
- `backend/scripts/run_jp_growth_pipeline.py`
- `backend/scripts/scheduled_crawl_runner.py`
- `backend/app/tasks/crawl_tasks.py`
- `backend/tests/`

## 実装タスク
1. Meta 専用 keyword rotation を静的商材語優先で安定運用する
2. duplicate guard と freshness を Meta 向けに調整する
3. `new saves / merged updates / backfilled creatives / backfilled LPs` を scheduler ログに出す
4. Meta だけの nightly / hourly backfill policy を整理する
5. token expiry 検知時の警告と fallback policy を入れる

## 完了条件
- [ ] Meta 新着取得の継続運転がしやすい
- [ ] merge と新規保存の内訳が追える
- [ ] backfill completion が scheduler から回せる
