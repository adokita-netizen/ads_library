# A28: ヒットスコア再校正 & ランキングアルゴリズム改善

## 目的
現在ほとんどの広告がスコア89-93に集中している。より差別化されたスコアリングに改善。

## タスク

### 1. 現在のスコア分布分析
- `backend/scripts/analyze_score_distribution.py` を作成
- ヒットスコアの分布(ヒストグラム)
- スコアと実際のメトリクス(再生数、いいね等)の相関分析

### 2. スコアリングアルゴリズム改善提案
- `backend/scripts/propose_new_scoring.py` を作成
- 正規化手法の提案(min-max, z-score, パーセンタイル)
- ジャンル内相対スコアリング
- 時系列ボーナス(新しい広告にブースト)

### 3. スコア再計算バッチ
- `backend/scripts/recalculate_scores.py` を作成
- 新アルゴリズムで全広告のスコアを再計算
- before/after比較レポート出力

## 制約
- rankings.py, media.pyは編集禁止
- backend/scripts/ にのみファイル作成
