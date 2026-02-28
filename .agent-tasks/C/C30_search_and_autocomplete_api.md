# C30: 検索 & オートコンプリートAPI

## 目的
広告検索の体験を向上。キーワード入力時のサジェスト、ファセット検索。

## タスク

### 1. GET /rankings/search/suggest
- クエリ: q=プロテ → ["プロテイン", "プロテインバー", ...]
- タイトル、広告主名、ジャンル名からサジェスト
- 最大10件返却

### 2. GET /rankings/search/facets
- 現在のフィルタ条件に基づくファセットカウント
- {genres: [{name: "スキンケア", count: 25}, ...], advertisers: [...]}

### 3. GET /rankings/search/advanced
- 複合検索: タイトルAND広告主ANDジャンルANDスコア範囲ANDメディアタイプ
- ソート: score, date, views, title
- ページネーション

## 技術要件
- rankings.py に追記(末尾に追加)
- SQLAlchemy ORMでクエリ構築
- _is_quality_ad()でフィルタ
