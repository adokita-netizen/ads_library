# A-R2-2: Metrics Delta Tracking
# 優先度: P0 | 前提: A-R2-1 | ブロック: ProRankingTable表示

## 目的
ProRankingTable の「再生増加数」「消化額増加」カラムに正しいデルタ値を表示するため、
日次メトリクスの前日比計算ロジックを実装する。

## 対象ファイル
- `backend/app/tasks/metrics_tasks.py` (修正)
- `backend/app/models/ad_metrics.py` (フィールド追加可)

## 現状
- AdDailyMetrics に view_count, spend, like_count 等の累計値がある
- フロント (ProRankingTable) は `view_increase`, `spend_increase`, `like_increase` を期待
- 現在これらのフィールドが NULL or 0 の可能性大

## 実装

### Step 1: AdDailyMetrics のデルタフィールド確認
```python
# ad_metrics.py を読んで既存フィールドを確認
# view_count_increase, spend_increase が既にあるか？
# 無ければ追加:
# view_count_increase = Column(BigInteger, default=0)
# spend_increase = Column(BigInteger, default=0)
# like_increase = Column(Integer, default=0)
```

### Step 2: metrics_tasks.py のデルタ計算実装
```python
def calculate_daily_deltas(session, ad_id, today_metrics):
    """前日のメトリクスとの差分を計算"""
    from datetime import timedelta

    yesterday = today_metrics.date - timedelta(days=1)
    prev = session.query(AdDailyMetrics).filter(
        AdDailyMetrics.ad_id == ad_id,
        AdDailyMetrics.date == yesterday
    ).first()

    if prev:
        today_metrics.view_count_increase = max(0, (today_metrics.view_count or 0) - (prev.view_count or 0))
        today_metrics.spend_increase = max(0, (today_metrics.spend or 0) - (prev.spend or 0))
        today_metrics.like_increase = max(0, (today_metrics.like_count or 0) - (prev.like_count or 0))
    else:
        # 初日は累計値をそのまま使う
        today_metrics.view_count_increase = today_metrics.view_count or 0
        today_metrics.spend_increase = today_metrics.spend or 0
        today_metrics.like_increase = today_metrics.like_count or 0
```

### Step 3: 既存データのバックフィル
```python
# 既存の全 AdDailyMetrics レコードに対してデルタを計算
# 新規スクリプト: backend/scripts/backfill_deltas.py
# ★ このファイルは Agent A の専有領域 (backend/scripts/ データ品質系)

def backfill_all_deltas():
    session = SyncSessionLocal()
    ads = session.query(Ad).all()
    for ad in ads:
        metrics = session.query(AdDailyMetrics).filter(
            AdDailyMetrics.ad_id == ad.id
        ).order_by(AdDailyMetrics.date.asc()).all()

        for i, m in enumerate(metrics):
            if i == 0:
                m.view_count_increase = m.view_count or 0
                m.spend_increase = m.spend or 0
            else:
                prev = metrics[i-1]
                m.view_count_increase = max(0, (m.view_count or 0) - (prev.view_count or 0))
                m.spend_increase = max(0, (m.spend or 0) - (prev.spend or 0))

    session.commit()
    session.close()
```

### Step 4: PRO RANKING API との接続確認
COORDINATION_LOG に記載:
```
[Planner 1 → Planner 2] AdDailyMetrics に view_count_increase, spend_increase, like_increase を追加/計算済み。
/pro-ranking のレスポンスでこれらを返すよう確認してください。
```

## 完了条件
- [ ] AdDailyMetrics にデルタフィールドが存在
- [ ] metrics_tasks.py にデルタ計算ロジックが組み込まれている
- [ ] 既存データのバックフィル完了
- [ ] view_count_increase が NULL の AdDailyMetrics: 0件
- [ ] status.md に結果記録
