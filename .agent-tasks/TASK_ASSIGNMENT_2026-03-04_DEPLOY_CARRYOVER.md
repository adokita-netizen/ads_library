# 2026-03-04 引き継ぎタスク（デプロイ）

## 状態サマリ（2026-03-03 時点）
- API Lambda デプロイ: 完了
- DB migration: 完了（`migration_complete`）
- 本番ヘルスチェック: `/health` と `/api/health` が 200
- Worker デプロイ: 実行中に中断（未完了）
- Frontend（S3 + CloudFront）デプロイ: 未実施

## 明日の優先タスク
1. Worker イメージ再ビルド・ECR push  
   - `vaap-production-worker:17668f8-local-20260303-01` を再作成して push
2. ECS タスク定義更新  
   - `vaap-production-worker` の container image を新タグへ更新
3. Frontend デプロイ  
   - `frontend` ビルド（export）→ `s3://vaap-production-frontend` sync
4. CloudFront キャッシュ削除  
   - Distribution: `ERPIU1B8ZZ5ZA`
5. 実機確認
   - 本番UIで `quick-crawl` 実行
   - 「同じ広告しか出ない」改善確認（検索結果の重複緩和・新着反映）

## 参考（今回反映済み修正）
- quick-crawl 500 修正（`best_image_url` 未初期化対策）
- `/rankings/search` の新着優先並び改善
- フロント検索パラメータ改善（`sort_by=relevance`, `page_size=200`）
- フロント重複表示緩和（簡易 dedupe）
