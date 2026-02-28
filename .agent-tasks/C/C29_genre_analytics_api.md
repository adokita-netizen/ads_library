# C29: ジャンル別分析API

## 目的
15ジャンルの詳細分析データを提供するAPIエンドポイント群を追加。

## タスク

### 1. GET /rankings/genres/distribution
- 各ジャンルの広告数、平均スコア、トレンド(増減)を返す
- レスポンス: [{genre, count, avg_score, trend_direction, top_ads}]

### 2. GET /rankings/genres/{genre}/details  
- 特定ジャンルの詳細分析
- トップ広告、平均メトリクス、時系列データ

### 3. GET /rankings/genres/comparison
- 複数ジャンルの横断比較
- クエリパラメータ: genres=スキンケア・美容,医療ダイエット

### 4. GET /rankings/genres/trends
- ジャンル別トレンド推移
- 週次/月次のジャンル構成変化

## 技術要件
- rankings.py に追記(末尾に追加)
- _is_quality_ad()でフィルタした品質広告のみ対象
- _resolve_fine_genre()でジャンル名解決
- flag_modified必須 for metadata更新
