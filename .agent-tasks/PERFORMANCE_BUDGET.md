# Performance Budget

最終更新: 2026-03-01

## 目的
フロントエンド・バックエンド双方のパフォーマンス目標値を定義し、
リグレッションを防止する基準線を設ける。

---

## Frontend Performance Budget

### Core Web Vitals 目標

| 指標 | 目標値 | 現状 | 担当 |
|------|--------|------|------|
| First Load JS | < 160kB | 150kB | B |
| LCP (Largest Contentful Paint) | < 2.5s | 未計測 | B |
| FID (First Input Delay) | < 100ms | 未計測 | B |
| CLS (Cumulative Layout Shift) | < 0.1 | 未計測 | B |
| TTI (Time to Interactive) | < 3.5s | 未計測 | B |
| TTFB (Time to First Byte) | < 800ms | 未計測 | B |

### Bundle Size Budget

| チャンク | 上限 | 備考 |
|---------|------|------|
| page.tsx (main) | < 50kB gzipped | エントリポイント |
| ProRankingView | < 30kB gzipped | 最重要ビュー |
| HitAdAnalysisView | < 40kB gzipped | 最大コンポーネント |
| AdDetailModal | < 25kB gzipped | モーダル |
| 各 lazy-loaded ビュー | < 20kB gzipped | dynamic import |
| 合計 First Load | < 160kB | next build 出力の First Load JS |

### リソース予算

| リソース | 上限 | 備考 |
|---------|------|------|
| 画像（1枚） | < 200kB | サムネイル: < 50kB |
| フォント | 0kB | システムフォント使用 |
| CSS | < 30kB gzipped | Tailwind purge 後 |
| API レスポンス（一覧） | < 500kB | ページネーション必須 |
| API レスポンス（詳細） | < 50kB | 1広告の全データ |

### コンポーネントレンダリング予算

| 操作 | 上限 | 備考 |
|------|------|------|
| テーブル初回描画（50行） | < 200ms | React profiler 計測 |
| テーブルソート切替 | < 100ms | useMemo 適用 |
| フィルター適用 | < 150ms | debounce 250ms |
| モーダル表示 | < 300ms | lazy load 含む |
| ページ遷移 | < 500ms | next/dynamic |
| 仮想スクロール（1000行） | < 16ms/frame | 60fps 維持 |

---

## Backend Performance Budget

### API レイテンシ目標

| エンドポイント | p50 | p95 | p99 | 担当 |
|--------------|-----|-----|-----|------|
| GET /rankings/hit-ads | < 200ms | < 500ms | < 1s | C |
| GET /rankings/pro-ranking | < 300ms | < 800ms | < 1.5s | C |
| GET /rankings/dashboard-summary | < 150ms | < 400ms | < 800ms | C |
| GET /rankings/score-breakdown/{id} | < 100ms | < 250ms | < 500ms | C |
| GET /rankings/genre-comparison | < 200ms | < 500ms | < 1s | C |
| GET /rankings/export?format=csv | < 2s | < 5s | < 10s | C |
| POST /rankings/quick-crawl | < 500ms | < 1s | < 2s | C+D |
| GET /media/thumbnail/{id} | < 100ms | < 300ms | < 500ms | D |
| GET /media/video/{id} | < 200ms | < 500ms | < 1s | D |
| POST /ai-chat/message | < 3s | < 5s | < 10s | C |

### DB クエリ予算

| クエリ | 上限 | 備考 |
|--------|------|------|
| 単一広告取得 | < 10ms | primary key |
| 広告一覧（50件） | < 100ms | インデックス使用 |
| ランキング計算 | < 500ms | 全広告スキャン |
| ジャンル集計 | < 200ms | GROUP BY |
| 全文検索 | < 300ms | trigram インデックス |
| メトリクスデルタ | < 150ms | 日次テーブル |

### バッチジョブ予算

| ジョブ | 上限 | 頻度 | 担当 |
|--------|------|------|------|
| メトリクス収集 | < 30min | 日次 | A |
| ヒットスコア再計算 | < 15min | 日次 | C |
| メディア抽出（100件） | < 2h | 週次 | D |
| データ品質チェック | < 10min | 日次 | A |
| LP クロール（50件） | < 1h | 週次 | D |
| 定期クロール（30件） | < 30min | 日次 | D |

### 接続プール予算

| リソース | 上限 | 備考 |
|---------|------|------|
| DB コネクション (API) | pool_size=5, max_overflow=10 | FastAPI |
| DB コネクション (Worker) | pool_size=2, max_overflow=3 | Celery |
| DB コネクション (Lambda) | pool_size=1 | Lambda |
| Redis コネクション | max=10 | Celery broker |
| HTTP クライアント | max=20 | aiohttp/requests |

---

## 監視・計測方法

### Frontend
```bash
# Bundle size check
npx next build --no-lint 2>&1 | grep "First Load JS"

# Lighthouse CI (ローカル)
npx lighthouse http://localhost:3000 --output=json --output-path=./lighthouse.json

# React profiler
# Chrome DevTools > Performance > Record でコンポーネント描画時間を確認
```

### Backend
```bash
# API レイテンシ計測
curl -w "\nTotal: %{time_total}s\n" http://localhost:8000/api/v1/rankings/hit-ads?limit=50

# DB クエリ時間（PostgreSQL）
# SET log_min_duration_statement = 100;  -- 100ms以上のクエリをログ

# バッチジョブ時間
time python scripts/recompute_hit_scores.py
```

---

## 違反時のアクション

| 違反レベル | 基準 | アクション |
|-----------|------|-----------|
| Warning | 目標値の 80-100% | CI ログに警告出力 |
| Error | 目標値の 100-150% | PR ブロック、改善タスク作成 |
| Critical | 目標値の 150%+ | 即座に修正、デプロイ停止 |

---

## 履歴

| 日付 | 変更 | 結果 |
|------|------|------|
| 2026-02-28 | B20: パフォーマンス最適化 | First Load JS: 305kB → 149kB (-52%) |
| 2026-03-01 | 現在値を基準線として設定 | 150kB |
