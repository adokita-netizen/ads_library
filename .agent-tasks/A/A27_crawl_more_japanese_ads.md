# A27: 日本語広告の大量取得 & ジャンルバランス改善

## 目的
現在133件の品質広告しかない。最低500件以上の日本語広告を確保し、ジャンルバランスを改善する。

## タスク

### 1. 不足ジャンルの特定と補充クロール用キーワード生成
- 現在のジャンル分布を分析
- 不足しているジャンル(金融・投資, アプリ, エンタメ, EC・通販)のクロール用検索キーワードを生成
- `backend/scripts/generate_crawl_keywords.py` に保存

### 2. Meta Ad Library APIを使った追加クロール
- `backend/scripts/crawl_japanese_ads.py` を作成
- 日本語広告のみをターゲット (country=JP, language=ja)
- 各ジャンルごとに最低30件ずつ取得を目標
- 既存のcrawling serviceを活用

### 3. データ品質チェック自動化
- `backend/scripts/auto_quality_check.py` を作成
- 自動スパム検出: タイトルが短すぎる、URL、非日本語
- 自動ジャンル分類: GENRE_RULES適用
- fine_genre_jpの自動付与

## 制約
- rankings.py, media.pyは編集禁止
- backend/scripts/ にのみファイル作成
