# パフォーマンス視点 — 遅い箇所と最適化ポイント

## 想定ボトルネック

### 1. rankings.py の巨大エンドポイント

**問題**: `/pro-ranking` は23パラメータを受け取り、SQL + Python レベルのフィルタリングを行う。
全広告をメモリにロードしてからPythonでフィルタリングしている可能性。

**確認方法**:
```bash
# レスポンス時間計測
time curl -s "http://localhost:8000/api/v1/rankings/pro-ranking?page=1&per_page=20" > /dev/null
```

**58件なら問題ないが、1000件超えると**:
- 全件ロード → Python フィルタ → ソート → ページング: O(n log n)
- SQLレベルで WHERE + ORDER BY + LIMIT: O(log n)

**対策**: SQL側にフィルタリングを寄せる。特に:
- genre フィルタ → `WHERE category = ?`
- platform フィルタ → `WHERE platform = ?`
- score range → `WHERE hit_score BETWEEN ? AND ?`
- ソート → `ORDER BY ? DESC LIMIT ? OFFSET ?`

### 2. Lambda コールドスタート

**問題**: FastAPI + 大量依存パッケージ = Lambda コールドスタート 5-15秒
**確認**: requirements.txt に PyTorch, Whisper, YOLOv8 が入っている
**影響**: 初回API呼び出しがタイムアウトする可能性

**対策**:
- Lambda レイヤーに重いライブラリを分離
- Lambda Provisioned Concurrency ($$$)
- または: Lambda にはAPI最小限、重い処理はECS
- フロントの api.ts に既にリトライロジックあり（502/503/504対応）

### 3. フロント初期ロード

**問題**: 22ビューの lazy import → 初期バンドルは軽いはず
**確認**: `out/` ディレクトリのサイズ

**潜在的問題**:
- HitAdAnalysisView.tsx が13回修正されて巨大化 → 遅延ロードでも重い
- Recharts, Lucide がバンドルサイズを大きくしている可能性

**確認方法**:
```bash
cd frontend
# バンドルサイズ分析
ANALYZE=true npx next build
# or
du -sh out/
du -sh .next/static/chunks/
```

### 4. 画像読み込み

**問題**: PRO DATABASE テーブルに20件 × サムネイル = 20回の画像リクエスト
各サムネイルが `/api/v1/media/thumbnail/{ad_id}` → Lambda → DB → 外部URLフェッチ

**対策**:
- S3にキャッシュ済みならpresigned URLを直接返す（Lambda経由不要）
- CloudFront でサムネイルをキャッシュ
- `loading="lazy"` は実装済み

### 5. N+1 クエリ問題

**問題**: `/pro-ranking` が広告一覧を返す際:
1. product_rankings テーブルから一覧取得 (1クエリ)
2. 各広告の ad テーブルを個別取得 (N クエリ)
3. 各広告の ad_metadata を個別取得 (N クエリ)

**対策**: JOIN で1クエリにまとめる
```sql
SELECT pr.*, a.title, a.thumbnail_url, a.ad_metadata
FROM product_rankings pr
JOIN ads a ON pr.ad_id = a.id
WHERE ...
ORDER BY ...
LIMIT 20 OFFSET 0
```

### 6. RDS 接続プール

**問題**: Lambda は各呼び出しで新しいDB接続を張る可能性
**確認**: `backend/app/core/database.py` の接続プール設定
**対策**:
- RDS Proxy の使用
- 接続プールの最大数制限
- Lambda の接続再利用パターン

---

## 計測すべきメトリクス

### API レスポンスタイム
```bash
# 主要エンドポイントのベンチマーク
for endpoint in \
  "rankings/pro-ranking?page=1&per_page=20" \
  "rankings/dashboard-summary" \
  "rankings/genre-master" \
  "rankings/hit-ads?limit=20" \
  "rankings/smart-autocomplete?query=test" \
  "media/thumbnail/1"; do
  TIME=$(curl -s -o /dev/null -w "%{time_total}" "http://localhost:8000/api/v1/$endpoint")
  echo "$endpoint: ${TIME}s"
done
```

### 目標値
| エンドポイント | 目標 | 許容最大 |
|---------------|------|---------|
| /pro-ranking | < 500ms | 2s |
| /dashboard-summary | < 300ms | 1s |
| /genre-master | < 200ms | 500ms |
| /hit-ads | < 500ms | 2s |
| /smart-autocomplete | < 100ms | 300ms |
| /media/thumbnail | < 200ms | 1s |

### フロント初期表示
| メトリクス | 目標 |
|-----------|------|
| First Contentful Paint | < 1.5s |
| Largest Contentful Paint | < 2.5s |
| Time to Interactive | < 3s |
| Bundle size (gzip) | < 300KB |

---

## 最適化の優先順位

```
[高効果・低コスト]
1. SQL フィルタリングを SQL 側に寄せる
2. N+1 クエリを JOIN に変更
3. CloudFront でサムネイルキャッシュ

[高効果・中コスト]
4. Lambda の依存パッケージ軽量化
5. React Query のキャッシュ戦略設定
6. rankings.py の分割

[中効果・高コスト]
7. RDS Proxy 導入
8. Lambda Provisioned Concurrency
9. フロントのバンドル最適化
```
