# KPI Definitions & Tracking

最終更新: 2026-03-01

## 目的
VAAP プラットフォームの成功指標を定義し、継続的に計測する。

---

## 1. データ品質 KPI (Agent A)

| KPI | 定義 | 目標値 | 計測方法 |
|-----|------|--------|---------|
| Data Completeness | 必須フィールドが全て埋まっている広告の割合 | >= 95% | `SELECT count(*) FROM ad WHERE title IS NOT NULL AND genre IS NOT NULL AND hit_score IS NOT NULL` / total |
| Metadata Completeness | ad_metadata 必須キーが全て存在する割合 | >= 90% | validate_metadata.py の出力 |
| Data Freshness | 直近24時間以内にクロールされた広告の割合 | >= 30% | `WHERE last_crawled_at > NOW() - INTERVAL '24 hours'` |
| NULL Score Rate | hit_score が NULL の広告の割合 | <= 5% | `WHERE hit_score IS NULL` / total |
| Delta Coverage | view_count_increase が計算済みの広告の割合 | >= 80% | ad_daily_metrics に2日分以上のレコードがある広告数 |
| Batch Success Rate | バッチジョブの成功率 | >= 98% | 成功回数 / 実行回数 |

### 計測クエリ
```sql
-- Data Completeness
SELECT
  ROUND(100.0 * COUNT(CASE WHEN title IS NOT NULL AND genre IS NOT NULL
    AND hit_score IS NOT NULL AND platform IS NOT NULL THEN 1 END) / COUNT(*), 1) AS completeness_pct
FROM ad;

-- NULL Score Rate
SELECT
  ROUND(100.0 * COUNT(CASE WHEN hit_score IS NULL THEN 1 END) / COUNT(*), 1) AS null_score_pct
FROM ad;

-- Data Freshness (requires last_crawled_at or created_at)
SELECT
  ROUND(100.0 * COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) / COUNT(*), 1) AS fresh_pct
FROM ad;
```

---

## 2. API パフォーマンス KPI (Agent C)

| KPI | 定義 | 目標値 | 計測方法 |
|-----|------|--------|---------|
| API Availability | API が正常に応答する時間の割合 | >= 99.5% | ヘルスチェック成功率 |
| p50 Latency | 50パーセンタイルのレスポンス時間 | <= 200ms | アクセスログ集計 |
| p95 Latency | 95パーセンタイルのレスポンス時間 | <= 800ms | アクセスログ集計 |
| Error Rate | 5xx エラーの割合 | <= 1% | 5xx 回数 / 全リクエスト |
| Query Count per Request | 1リクエストあたりの SQL 実行数 | <= 5 | SQL ログ集計 |
| Response Size (avg) | 平均レスポンスサイズ | <= 200kB | Content-Length 集計 |

### 計測方法
```bash
# p95 レイテンシ（ローカル計測）
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{time_total}\n" http://localhost:8000/api/v1/rankings/hit-ads?limit=50
done | sort -n | sed -n '95p'

# エラー率（ログから）
grep -c "HTTP/1.1 5" /var/log/vaap/access.log
```

---

## 3. フロントエンド UX KPI (Agent B)

| KPI | 定義 | 目標値 | 計測方法 |
|-----|------|--------|---------|
| First Load JS | 初回ロードの JS バンドルサイズ | <= 160kB | `npx next build` 出力 |
| LCP | Largest Contentful Paint | <= 2.5s | Lighthouse |
| FID | First Input Delay | <= 100ms | Lighthouse |
| CLS | Cumulative Layout Shift | <= 0.1 | Lighthouse |
| Component Count | 登録コンポーネント数 | 追跡のみ | `ls src/components/**/*.tsx | wc -l` |
| View Count | 登録ビュー数 | 追跡のみ | page.tsx の ViewType 数 |
| Error Boundary Triggers | Error Boundary がキャッチしたエラー数 | <= 5/週 | ログ集計 |
| Loading State Coverage | ローディング状態が実装されているビューの割合 | 100% | 手動確認 |

---

## 4. メディア品質 KPI (Agent D)

| KPI | 定義 | 目標値 | 計測方法 |
|-----|------|--------|---------|
| Image Coverage | image_url が存在する広告の割合 | >= 99% | `WHERE image_url IS NOT NULL` |
| Thumbnail Coverage | thumbnail_url が存在する広告の割合 | >= 95% | `WHERE thumbnail_url IS NOT NULL` |
| Video Coverage | video_url が存在する動画広告の割合 | >= 90% | `WHERE creative_type='video' AND video_url IS NOT NULL` |
| S3 Cache Rate | S3 にキャッシュされているメディアの割合 | >= 80% | `WHERE image_s3_key IS NOT NULL` |
| Media Quality Score | 品質チェック通過率 | >= 90% | validate_extracted_media.py |
| Extraction Success Rate | メディア抽出の成功率 | >= 85% | `WHERE media_extraction_status='completed'` |
| Crawl Success Rate | クロールの成功率 | >= 90% | 成功件数 / 実行件数 |

### 計測クエリ
```sql
-- Media Coverage Summary
SELECT
  COUNT(*) AS total,
  COUNT(CASE WHEN image_url IS NOT NULL THEN 1 END) AS has_image,
  COUNT(CASE WHEN thumbnail_url IS NOT NULL THEN 1 END) AS has_thumbnail,
  COUNT(CASE WHEN video_url IS NOT NULL AND creative_type = 'video' THEN 1 END) AS has_video,
  COUNT(CASE WHEN image_s3_key IS NOT NULL THEN 1 END) AS has_s3_cache,
  COUNT(CASE WHEN media_extraction_status = 'completed' THEN 1 END) AS extraction_done
FROM ad;
```

---

## 5. 運用 KPI (全体)

| KPI | 定義 | 目標値 | 計測方法 |
|-----|------|--------|---------|
| CI Task Burn Rate | 週あたりの CI タスク消化数 | >= 3 | CONTINUOUS_IMPROVEMENT_BACKLOG.md の [DONE] 数 |
| P0 Task Backlog | 未着手の P0 タスク数 | <= 3 | CI バックログ集計 |
| Incident Count | 月あたりの障害発生数 | <= 2 | INCIDENT_RUNBOOK.md 利用回数 |
| Mean Time to Recovery | 障害からの復旧時間 | <= 1h | 障害記録 |
| Deploy Frequency | デプロイ頻度 | >= 1/週 | デプロイ記録 |
| Agent Utilization | エージェントのタスク実行率 | >= 80% | 進捗トラッカー |

---

## 6. ビジネス KPI (将来)

| KPI | 定義 | 目標値 | 備考 |
|-----|------|--------|------|
| Total Ads Tracked | 追跡中の広告総数 | 1000+ | Phase 3 目標 |
| Active Genres | アクティブなジャンル数 | 10+ | ジャンル多様性 |
| HIT Detection Accuracy | HIT 判定の精度 | >= 80% | 人間レビュー比較 |
| User Satisfaction | ユーザー満足度 | >= 4/5 | フィードバック |
| Data-to-Insight Latency | データ取得→分析結果表示までの時間 | <= 6h | パイプライン全体 |

---

## ダッシュボード表示

これらの KPI は以下で可視化:
1. **ProRankingView**: リアルタイムのランキングデータ
2. **DashboardSummary**: サマリーカードで主要 KPI を表示
3. **DataQuality API** (A-R3-1): データ品質の時系列推移
4. **COORDINATION_LOG.md**: CI 消化率の定期記録

---

## 計測スクリプト

```bash
#!/bin/bash
# kpi_snapshot.sh — KPI スナップショット
# Usage: bash .agent-tasks/kpi_snapshot.sh

echo "=== VAAP KPI Snapshot ==="
echo "$(date '+%Y-%m-%d %H:%M')"
echo ""

# Data Quality
echo "--- Data Quality ---"
psql -t -c "SELECT 'Total ads: ' || COUNT(*) FROM ad;" 2>/dev/null || echo "  DB not available"
psql -t -c "SELECT 'NULL score: ' || COUNT(CASE WHEN hit_score IS NULL THEN 1 END) FROM ad;" 2>/dev/null

# Media
echo "--- Media ---"
psql -t -c "SELECT 'Has image: ' || COUNT(CASE WHEN image_url IS NOT NULL THEN 1 END) FROM ad;" 2>/dev/null
psql -t -c "SELECT 'S3 cached: ' || COUNT(CASE WHEN image_s3_key IS NOT NULL THEN 1 END) FROM ad;" 2>/dev/null

# Frontend
echo "--- Frontend ---"
cd frontend 2>/dev/null && npx next build --no-lint 2>&1 | grep "First Load JS" || echo "  Frontend not available"

# CI
echo "--- CI Backlog ---"
ci_done=$(grep -c "\\[DONE" .agent-tasks/CONTINUOUS_IMPROVEMENT_BACKLOG.md 2>/dev/null || echo 0)
ci_total=$(grep -c "^- CI-" .agent-tasks/CONTINUOUS_IMPROVEMENT_BACKLOG.md 2>/dev/null || echo 0)
echo "  Done: $ci_done / $ci_total"
```
