# Agent C タスク: トレンド分析 & ジャンル比較API

## 方向性
スコアリングと基本分析APIは完成した。
次は「時間軸」と「比較」の分析。広告が今どういうトレンドにあるか、
ジャンル間でどう違うかを可視化するためのAPIを作る。

## やってほしいこと（優先順に）

### 1. ジャンル別比較API
`GET /rankings/genre-comparison`
- 各ジャンル（ad_category）ごとの統計: 広告数, 平均スコア, hit率, mega_hit率, 平均days_running
- ジャンル間の比較がフロントエンドで表やチャートにできる形式で返す
- ジャンルがNULLの広告は "uncategorized" として扱う

### 2. 配信期間分析API
`GET /rankings/duration-brackets`
- 配信日数を区間に分けて分析: 0-7日, 8-14日, 15-30日, 31-60日, 61-90日, 91日+
- 各区間の広告数, 平均スコア, hit率
- 「長く配信されている広告ほどスコアが高い」等の相関を見せるデータ

### 3. クリエイティブタイプ別分析API
`GET /rankings/creative-analysis`
- video vs image vs carousel の比較
- 各タイプの平均スコア, hit率, 平均配信日数
- 動画がある広告とない広告でスコアに差があるか

### 4. サマリーダッシュボードAPI
`GET /rankings/dashboard-summary`
- フロントのダッシュボード上部に表示するKPI用データをまとめて返す
- total_ads, active_ads, hit_count, mega_hit_count, avg_score, avg_days_running
- top_genre（最もhit率が高いジャンル）, top_creative_type
- 1回のAPIコールで全サマリーが取れるようにする

## 制約
- INSTRUCTIONS.md のコンフリクト防止ルール厳守
- 修正ファイル: `backend/app/api/endpoints/rankings.py` のみ
- 必要なら `ranking_service.py` にヘルパー関数追加OK
- 既存エンドポイントを壊さない
- import確認: `cd C:/Users/ishit/ads_library/backend && python -c "from app.api.endpoints.rankings import router"`
