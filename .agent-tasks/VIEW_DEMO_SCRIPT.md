# デモスクリプト視点 — 5分間デモで何を見せるか

## デモの目的
「VAAP は動画広告の競合分析を自動化し、ヒット広告のパターンを発見するAIプラットフォーム」

---

## 5分デモスクリプト

### 0:00-0:30 — オープニング
「今日は VAAP — Video Ad Analysis AI Platform をお見せします。
競合の動画広告を自動収集・分析して、ヒットのパターンを見つけるツールです。」

**画面**: PRO DATABASE テーブルが表示されている

### 0:30-1:30 — PRO DATABASE（メイン機能）
「これがメインのランキング画面です。」

**操作**:
1. テーブルをスクロール → 「広告がランキング形式で並んでいます」
2. HITLINEバッジを指す → 「金色の行がヒットラインを超えた広告です」
3. スコア列を指す → 「独自のヒットスコアで自動判定しています」

**ポイント**: サムネイルが表示されていること、数値が入っていること

### 1:30-2:30 — フィルタリング＆検索
「ジャンルで絞り込めます。」

**操作**:
1. サイドバーで「美容」をクリック → テーブルがフィルタ
2. 検索バーに「サプリ」入力 → オートコンプリート表示
3. プラットフォームフィルター → Facebook のみ

**ポイント**: レスポンスが速いこと、日本語検索が動くこと

### 2:30-3:30 — 広告詳細
「広告をクリックすると詳細が見えます。」

**操作**:
1. ヒット広告の行をクリック → AdDetailModal が開く
2. 動画/画像プレビューを見せる
3. スコア内訳 → 「5つのシグナルで分析しています」
4. 「LPを見る」ボタン → LP に遷移

**ポイント**: CreativeViewer にメディアが表示されること

### 3:30-4:30 — 分析機能
「ヒットパターンの分析もできます。」

**操作**:
1. サイドバー「ヒット広告分析」→ HitAdAnalysisView
2. サマリーカード → 「ヒット率、平均スコア、トップジャンル」
3. ジャンル比較チャート → 「どのジャンルがヒットしやすいか」
4. 勝ちパターン → 「フック × CTA × オファーの組み合わせ」

### 4:30-5:00 — クロージング
「さらに AI でクリエイティブ生成、LP分析、動画書き起こしなども対応しています。
データが増えるほど分析精度が上がります。」

---

## デモ前チェックリスト

### データ準備
- [ ] 200件以上の広告がDBにある
- [ ] 3ジャンル以上にデータ分布（美容、健康食品、ダイエット最低）
- [ ] ヒットスコアが計算済み（HIT/大HIT が各5件以上）
- [ ] サムネイルが80%以上表示可能
- [ ] 少なくとも5件に動画URLがある

### 動作確認
- [ ] PRO DATABASE テーブルがロードされる（3秒以内）
- [ ] ジャンルフィルタリングが動く
- [ ] 検索オートコンプリートが動く
- [ ] AdDetailModal が正しく開く
- [ ] HitAdAnalysisView が表示される
- [ ] エクスポートが動く

### 避けるべき操作（デモ中）
- ❌ AI生成機能（APIキー未設定なら動かない）
- ❌ Meta広告管理（トークン未設定）
- ❌ チームスペース（未完成）
- ❌ カレンダー（データ不足）
- ❌ VAAPストア（未完成）

---

## デモ用データの準備スクリプト

```bash
cd C:/Users/ishit/ads_library/backend

# 1. 既存データの分析実行
python -m scripts.classify_ads
python -m scripts.fix_titles
python -m scripts.fix_destination_urls
python -m scripts.collect_delivery_dates
python -m scripts.check_ad_survival

# 2. スコア計算
python -m scripts.recompute_hit_scores

# 3. サムネイル修復
python -m scripts.fix_bad_thumbnails

# 4. 確認
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import ProductRanking
s = SyncSessionLocal()
total = s.query(Ad).count()
with_cat = s.query(Ad).filter(Ad.category != None).count()
with_score = s.query(ProductRanking).count()
hits = s.query(ProductRanking).filter(ProductRanking.is_hit == True).count()
print(f'Ads: {total}, Categorized: {with_cat}, Scored: {with_score}, Hits: {hits}')
s.close()
"
```

---

## スクリーンショット撮影ポイント

ドキュメント/プレゼン用に以下の画面をキャプチャ:

1. **PRO DATABASE 全体** — ランキングテーブルの全景
2. **HIT広告ハイライト** — 金色背景のHITLINE行
3. **検索サジェスト** — オートコンプリートドロップダウン
4. **広告詳細モーダル** — スコア内訳 + メディアプレビュー
5. **ジャンル比較チャート** — 横棒グラフ
6. **サマリーカード** — 6枚のKPIカード

---

## デモ失敗時のリカバリー

### 画面が白い
→ F5でリロード。それでもダメなら「開発版のため再起動します」と言ってバックエンド再起動。

### サムネイルが全部壊れている
→ 「実際のメディアはクラウドストレージにキャッシュ中です」と説明して、テキスト情報に集中。

### APIが遅い (Lambdaコールドスタート)
→ デモ5分前にサイトを開いておいてウォームアップ。

### データが少なく見える
→ 「テスト環境のため限定データですが、本番では数千件を常時収集しています」

### スコアが全部同じ
→ 「分析パイプラインを実行中です。完了後はスコアに差が出ます」
