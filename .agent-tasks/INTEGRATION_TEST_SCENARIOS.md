# Integration Test Scenarios (Cross-Agent)

最終更新: 2026-03-01

## 目的
エージェント間の結合点でデータが正しく流れることを検証するシナリオ集。
各シナリオには「前提条件」「実行手順」「期待結果」を定義する。

---

## IT-001: クロール → データ品質 → スコア計算 → UI表示

### パイプライン
```
D (crawl) → A (data quality) → C (hit score) → B (UI display)
```

### 前提条件
- Meta API トークンが有効
- PostgreSQL に接続可能
- フロントエンドが起動中

### 手順
1. **D**: `POST /api/v1/rankings/quick-crawl` でキーワード「美容」、limit=5 を実行
2. **A**: クロール完了後、`python scripts/classify_ads.py` でジャンル分類を実行
3. **A**: `python scripts/fix_titles.py` でタイトル正規化
4. **C**: `python scripts/recompute_hit_scores.py` でヒットスコア再計算
5. **B**: `/api/v1/rankings/hit-ads` のレスポンスに新規広告が含まれることを確認

### 期待結果
- 新規広告が DB に保存されている（`ad` テーブル）
- `ad_metadata` に `creative_quality`, `is_still_running` が設定されている
- `hit_score` が NULL でない
- フロントエンドの ProRankingTable に表示される

### 検証クエリ
```sql
SELECT id, title, hit_score, genre,
       ad_metadata->>'creative_quality' as quality,
       ad_metadata->>'is_still_running' as running
FROM ad
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;
```

---

## IT-002: メトリクス収集 → デルタ計算 → ランキング更新

### パイプライン
```
D (crawl metrics) → A (delta calc) → C (ranking update) → B (display)
```

### 手順
1. **A**: `python scripts/collect_real_metrics.py` を2日連続で実行（または手動で2レコード作成）
2. **A**: `view_count_increase` = 今日の `view_count` - 昨日の `view_count` を計算
3. **C**: `/api/v1/rankings/pro-ranking` が `view_count_increase` を含むことを確認
4. **B**: ProRankingTable の「再生増加数」カラムに値が表示されることを確認

### 期待結果
- `ad_daily_metrics` に2日分のレコードが存在
- デルタ値が正しく計算されている
- ランキングAPIのレスポンスに `view_count_increase` フィールドが存在
- UI の再生増加数カラムに `+XX,XXX` 形式で表示

---

## IT-003: メディア抽出 → サムネイルキャッシュ → UI画像表示

### パイプライン
```
D (extract media) → D (cache to S3) → C (proxy API) → B (display)
```

### 手順
1. **D**: `python -m celery -A app.tasks call app.tasks.media_tasks.extract_media_task --args='[AD_ID]'`
2. **D**: `image_s3_key` と `thumbnail_s3_key` が設定されたことを確認
3. **C**: `GET /api/v1/media/thumbnail/{AD_ID}` がリダイレクトまたは画像を返すことを確認
4. **B**: ProRankingTable/AdDetailModal でサムネイルが表示されることを確認

### 期待結果
- S3 に画像がアップロードされている
- プロキシ API が 200/302 を返す
- UI で画像が表示される（プレースホルダーでない）

---

## IT-004: LP分析 → スコア統合 → UI表示

### パイプライン
```
D (LP crawl) → A (LP data) → C (LP score API) → B (LP panel)
```

### 手順
1. **D**: LP ページをクロール（`destination_url` が存在する広告を選択）
2. **A**: LP メタデータ（title, description, og:image）を `ad_metadata` に保存
3. **C**: `GET /api/v1/rankings/lp-analysis/{AD_ID}` が LP データを返すことを確認
4. **B**: AdDetailModal の LP セクションにデータが表示されることを確認

### 期待結果
- `ad_metadata` に LP 関連データが存在
- LP 分析 API がスクリーンショット URL、タイトル、説明文を返す
- UI で LP 情報が表示される

---

## IT-005: ヒット判定 → 通知生成 → UI通知

### パイプライン
```
C (hit score calc) → C (alert check) → C (notification API) → B (notification center)
```

### 手順
1. **C**: 特定の広告のヒットスコアを手動で閾値超え（score >= 60）に設定
2. **C**: アラートルールが発火し、通知が生成されることを確認
3. **B**: 通知センターのベルアイコンに未読バッジが表示されることを確認
4. **B**: 通知ドロップダウンに「新しいHIT広告を検出」メッセージが表示されることを確認

### 期待結果
- `notifications` テーブルにレコードが作成される
- `GET /api/v1/notifications` が未読通知を返す
- UI のベルアイコンに数字バッジ
- 通知をクリックすると既読になる

---

## IT-006: エクスポート → ダウンロード → 整合性検証

### パイプライン
```
B (export request) → C (export API) → B (download)
```

### 手順
1. **B**: HitAdAnalysisView のエクスポートドロップダウンから CSV を選択
2. **C**: `GET /api/v1/rankings/export?format=csv` が CSV ファイルを返すことを確認
3. **B**: ダウンロードが開始されることを確認
4. CSV の行数が UI のテーブル行数と一致することを確認

### 期待結果
- CSV が正しい UTF-8 エンコーディング
- ヘッダー行 + データ行数がフィルター適用後のカウントと一致
- 数値フィールドが正しくフォーマットされている

---

## IT-007: バルクメディアダウンロード

### パイプライン
```
B (select ads) → C (bulk download API) → D (zip creation) → B (download)
```

### 手順
1. **B**: テーブルでチェックボックスで3件選択
2. **B**: 「3件DL」ボタンをクリック
3. **C**: 各広告の `/api/v1/media/download/{AD_ID}` が呼ばれることを確認
4. ダウンロードが開始されることを確認

### 期待結果
- 各広告の画像/動画ファイルがダウンロードされる
- ファイル名に広告IDが含まれる

---

## IT-008: 検索 → フィルター → ソート → ページネーション

### パイプライン
```
B (search input) → C (search API) → B (display)
```

### 手順
1. **B**: SmartSearchBar に「ダイエット」を入力
2. **C**: `GET /api/v1/rankings/pro-ranking?search=ダイエット` のレスポンスを確認
3. **B**: ジャンルフィルターで「美容」を選択
4. **B**: スコアの降順でソート
5. **B**: ページ2に移動

### 期待結果
- 検索結果がキーワードに関連する広告のみ含む
- フィルターが正しく適用される
- ソート順が正しい
- ページネーションが正しく動作する（totalCount, hasMore）

---

## IT-009: ダークモード切替 → 全画面適用

### 手順
1. **B**: テーマトグルボタンをクリック
2. `<html>` に `class="dark"` が追加されることを確認
3. 5つの主要画面を巡回
4. localStorage に `theme: "dark"` が保存されることを確認
5. ページリロード後もダークモードが維持されることを確認

### 期待結果
- 全画面の背景が暗色に切り替わる
- テキストが読みやすい色に切り替わる
- チャート/グラフの色が暗色テーマに適応
- カード/モーダルのボーダーが暗色テーマに適応

---

## IT-010: AI チャット → 構造化レスポンス → UI表示

### パイプライン
```
B (chat input) → C (ai-chat API) → C (intent classify + response) → B (display)
```

### 手順
1. **B**: AIチャットUIを開く
2. 「美容ジャンルのヒット広告を分析して」と入力
3. **C**: `POST /api/v1/ai-chat/message` でインテント分類が実行される
4. **C**: `analyze_genre` インテントとして処理される
5. **B**: 構造化されたレスポンスが表示される

### 期待結果
- インテントが正しく分類される
- レスポンスに分析データが含まれる
- UI でマークダウン形式のレスポンスが表示される

---

## 自動化スクリプト

```bash
#!/bin/bash
# integration_smoke.sh — 統合スモークテスト
# Usage: bash .agent-tasks/integration_smoke.sh

echo "=== VAAP Integration Smoke Test ==="
echo "$(date '+%Y-%m-%d %H:%M')"
echo ""

BASE_URL="${VAAP_API_URL:-http://localhost:8000/api/v1}"
PASS=0
FAIL=0

check() {
  local name=$1
  local url=$2
  local expected_status=${3:-200}

  status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
  if [ "$status" = "$expected_status" ]; then
    echo "  [PASS] $name (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name (expected $expected_status, got $status)"
    FAIL=$((FAIL + 1))
  fi
}

echo "--- API Health ---"
check "Health" "$BASE_URL/../health"

echo "--- Rankings API ---"
check "Hit Ads" "$BASE_URL/rankings/hit-ads?limit=5"
check "Pro Ranking" "$BASE_URL/rankings/pro-ranking?limit=5"
check "Dashboard Summary" "$BASE_URL/rankings/dashboard-summary"
check "Genre Comparison" "$BASE_URL/rankings/genre-comparison"
check "Score Distribution" "$BASE_URL/rankings/score-distribution"

echo "--- Media API ---"
check "Media List" "$BASE_URL/media/status"

echo "--- Search API ---"
check "Autocomplete" "$BASE_URL/rankings/smart-autocomplete?q=beauty"

echo "--- Trends API ---"
check "Weekly Trends" "$BASE_URL/rankings/trends/weekly"
check "Market Overview" "$BASE_URL/rankings/trends/market-overview"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
```

---

## テスト実行頻度

| シナリオ | 頻度 | 自動化 |
|---------|------|--------|
| IT-001 | 週1回 | 手動（トークン要） |
| IT-002 | 日次 | 自動化予定 |
| IT-003 | デプロイ後 | 手動 |
| IT-004 | 週1回 | 手動 |
| IT-005 | Phase 2 完了後 | 手動 |
| IT-006 | デプロイ後 | スモーク |
| IT-007 | デプロイ後 | 手動 |
| IT-008 | デプロイ後 | スモーク |
| IT-009 | B-R2-1 完了後 | 手動 |
| IT-010 | Phase 2 完了後 | 手動 |
