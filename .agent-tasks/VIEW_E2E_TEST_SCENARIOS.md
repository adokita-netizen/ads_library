# E2Eテストシナリオ視点 — エージェント横断で壊れやすいフロー

## なぜこの視点が必要か
各エージェントは自分の領域だけテストする。
だが、実際のユーザー操作はエージェント境界を跨ぐ。
壊れるのは常に「境界」。

---

## Scenario 1: 広告が画面に表示されるまで

```
[Agent D] クロール → DB INSERT
[Agent A] 分類 → category UPDATE
[Agent C] スコア計算 → product_rankings INSERT
[Agent C] API → /pro-ranking JSON レスポンス
[Agent B] ProRankingTable → テーブル描画
```

### テスト手順:
1. DBに新しい広告を1件INSERT（テストデータ）
2. `classify_ads` でカテゴリ付与
3. `recompute_hit_scores` でスコア計算
4. `/api/v1/rankings/pro-ranking` を叩いてその広告が含まれるか確認
5. フロントで PRO DATABASE を開いてその広告が表示されるか確認

### 壊れやすいポイント:
- [ ] category が NULL → ジャンルフィルターに引っかからない
- [ ] product_rankings にレコードがない → API に出てこない
- [ ] APIのフィールド名がフロントの期待と違う
- [ ] サムネイルURLが403 → 画像が壊れる

---

## Scenario 2: サムネイルが表示されるまで

```
[Agent D] extract_missing_videos → thumbnail_url 取得
[Agent D] fix_bad_thumbnails → S3アップロード → thumbnail_s3_key
[Agent C] API → /media/thumbnail/{ad_id} → プロキシ or S3 presigned URL
[Agent B] <img src={proxyUrl} onError={fallback}> → 表示
```

### テスト手順:
1. 広告1件の thumbnail_url を確認
2. `/api/v1/media/thumbnail/{ad_id}` を叩いて画像が返るか
3. フロントでその広告のサムネイルが表示されるか

### 壊れやすいポイント:
- [ ] thumbnail_url が NULL → プロキシAPIが何を返すか
- [ ] S3にアップロード済みだが presigned URL が期限切れ
- [ ] CloudFront キャッシュで古い403レスポンスがキャッシュされている
- [ ] フロントの onError フォールバックチェーンが正しく動くか

---

## Scenario 3: ヒットスコアが詳細モーダルに表示されるまで

```
[Agent A] メトリクス収集 → ad_metadata に estimated_*, days_running
[Agent C] スコア計算 → ad_metadata に latest_hit_score, hit_level
[Agent C] API → /rankings/score-breakdown/{ad_id} → 5シグナル詳細
[Agent B] AdDetailModal → スコアバー + シグナル内訳表示
```

### テスト手順:
1. 広告1件の ad_metadata を確認（estimated_*, days_running が入っているか）
2. `recompute_hit_scores` を実行
3. ad_metadata に latest_hit_score, hit_level が入ったか確認
4. `/api/v1/rankings/score-breakdown/{ad_id}` を叩く
5. フロントで詳細モーダルを開いてスコアが表示されるか

### 壊れやすいポイント:
- [ ] Agent A のメトリクスが未収集 → スコア計算の入力がない → 全部0点
- [ ] score-breakdown API が ad_id に対して404を返す
- [ ] フロントが score_breakdown のキー名を間違えている（snake_case vs camelCase）

---

## Scenario 4: 検索してフィルタリング

```
[Agent A] classify_ads → category
[Agent C] genre-master API → ジャンル階層
[Agent C] smart-autocomplete API → サジェスト
[Agent C] pro-ranking API → フィルタリング結果
[Agent B] SmartSearchBar → サジェスト表示
[Agent B] ProRankingTable → フィルタ適用後テーブル
```

### テスト手順:
1. 「美容」と入力 → オートコンプリートにジャンル候補が出るか
2. ジャンル選択 → テーブルがフィルタリングされるか
3. テキスト検索 → 商材名/広告主名で絞り込めるか

### 壊れやすいポイント:
- [ ] 分類未実行 → ジャンルが全部NULL → フィルタリング不可
- [ ] genre-master のカテゴリ名と ads.category の値が一致しない
- [ ] autocomplete が日本語で動かない（エンコーディング問題）

---

## Scenario 5: CSV エクスポート

```
[Agent A] 全データ品質スクリプト実行 → 完全なデータ
[Agent C] export/csv API → CSVファイル生成
[Agent B] エクスポートボタン → ファイルダウンロード
```

### テスト手順:
1. PRO DATABASE でフィルターを適用
2. エクスポートボタン → CSV選択
3. ファイルがダウンロードされるか
4. CSVの中身が正しいか（列名、文字化け、件数）

### 壊れやすいポイント:
- [ ] フロントが `/export/csv` を叩くURLが間違っている
- [ ] CSVの文字コード（UTF-8 BOM なしだとExcelで文字化け）
- [ ] フィルター条件がAPIに正しく渡らない

---

## Scenario 6: 広告詳細 → LP遷移

```
[Agent A] fix_destination_urls → destination_url
[Agent C] API → /pro-ranking の destination_url フィールド
[Agent B] AdDetailModal → 「LPを見る」ボタン → window.open(url)
```

### テスト手順:
1. destination_url がある広告を特定
2. 詳細モーダルを開く
3. 「LPを見る」ボタンが表示されるか
4. クリックで新タブが開くか
5. LP が実際に表示されるか

### 壊れやすいポイント:
- [ ] destination_url が NULL → ボタンが表示されない
- [ ] URL がリダイレクト前の短縮URL → 404
- [ ] HTTPS でない URL → ブラウザ警告

---

## 自動テストスクリプト（将来用）

```bash
#!/bin/bash
# E2E smoke test

BASE_URL="http://localhost:8000/api/v1"

echo "=== API Health ==="
curl -s "$BASE_URL/../health" | python -m json.tool

echo "=== Genre Master ==="
curl -s "$BASE_URL/rankings/genre-master" | python -c "
import json,sys
d=json.load(sys.stdin)
print(f'Genres: {len(d.get(\"items\",d.get(\"groups\",[])))} groups')
"

echo "=== Pro Ranking ==="
curl -s "$BASE_URL/rankings/pro-ranking?page=1&per_page=5" | python -c "
import json,sys
d=json.load(sys.stdin)
items=d.get('items',[])
print(f'Items: {len(items)}, Total: {d.get(\"total\",0)}')
if items:
    i=items[0]
    print(f'First: rank={i.get(\"rank\")}, name={i.get(\"product_name\")}, score={i.get(\"hit_score\")}')
    print(f'  thumb={bool(i.get(\"thumbnail_url\"))}, genre={i.get(\"genre\")}, dest={bool(i.get(\"destination_url\"))}')
"

echo "=== Dashboard Summary ==="
curl -s "$BASE_URL/rankings/dashboard-summary" | python -c "
import json,sys
d=json.load(sys.stdin)
print(f'Total: {d.get(\"total_ads\")}, Active: {d.get(\"active_ads\")}, Hits: {d.get(\"hit_count\")}, Avg: {d.get(\"avg_score\")}')
"

echo "=== Autocomplete ==="
curl -s "$BASE_URL/rankings/smart-autocomplete?query=美容" | python -c "
import json,sys
d=json.load(sys.stdin)
sug=d.get('suggestions',[])
print(f'Suggestions: {len(sug)}')
for s in sug[:3]: print(f'  {s.get(\"type\")}: {s.get(\"label\")}')
"

echo "=== Score Breakdown (first ad) ==="
AD_ID=$(curl -s "$BASE_URL/rankings/pro-ranking?page=1&per_page=1" | python -c "
import json,sys
d=json.load(sys.stdin)
items=d.get('items',[])
print(items[0]['ad_id'] if items else '')
")
if [ -n "$AD_ID" ]; then
    curl -s "$BASE_URL/rankings/score-breakdown/$AD_ID" | python -m json.tool | head -20
fi

echo "=== Thumbnail Proxy ==="
if [ -n "$AD_ID" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/media/thumbnail/$AD_ID")
    echo "Thumbnail HTTP: $HTTP_CODE"
fi

echo "=== Export CSV ==="
CSV_SIZE=$(curl -s "$BASE_URL/rankings/export/csv?genre=all" | wc -c)
echo "CSV size: $CSV_SIZE bytes"

echo "=== Done ==="
```
