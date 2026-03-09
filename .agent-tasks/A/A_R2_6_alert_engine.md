# A-R2-6: Smart Alert Engine (A37 Phase 2)
# 優先度: P2 | 前提: A-R2-1〜5 完了 | ブロック: C39 (通知API)

## 目的
条件ベースのアラートルール定義 + 評価エンジン + アラート履歴記録

## 対象ファイル (全て Agent A 専有)
- 新規: `backend/app/models/alert_rule.py`
- 新規: `backend/app/models/alert_history.py`
- 新規: `backend/app/services/alert_engine.py`
- 新規: `backend/app/services/data_freshness.py`

## 実装

### 1. AlertRule モデル
```python
# backend/app/models/alert_rule.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from app.core.database import Base
from datetime import datetime

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500))
    condition_type = Column(String(50), nullable=False)
    # Types: "score_threshold", "score_change", "new_hit", "data_quality", "crawl_failure"
    target_field = Column(String(100))  # e.g., "hit_score", "view_count"
    operator = Column(String(10))       # "gt", "lt", "eq", "change_gt"
    threshold = Column(Float)
    genre_filter = Column(String(100))  # NULL = all genres
    is_active = Column(Boolean, default=True)
    notification_channel = Column(String(50), default="in_app")  # in_app, slack, email
    cooldown_minutes = Column(Integer, default=60)  # 同一ルールの再発火防止
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default={})
```

### 2. AlertHistory モデル
```python
# backend/app/models/alert_history.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from app.core.database import Base
from datetime import datetime

class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    ad_id = Column(Integer, ForeignKey("ads.id"), nullable=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    alert_type = Column(String(50))      # same as condition_type
    severity = Column(String(20), default="info")  # info, warning, critical
    title = Column(String(300))
    message = Column(String(1000))
    old_value = Column(Float)
    new_value = Column(Float)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    metadata = Column(JSON, default={})
```

### 3. AlertEngine サービス
```python
# backend/app/services/alert_engine.py
from datetime import datetime, timedelta
from app.models.alert_rule import AlertRule
from app.models.alert_history import AlertHistory
from app.models.ad import Ad

class AlertEngine:
    def __init__(self, session):
        self.session = session

    def evaluate_all_rules(self):
        """全アクティブルールを評価し、条件合致時にアラート生成"""
        rules = self.session.query(AlertRule).filter(AlertRule.is_active == True).all()
        alerts_generated = 0

        for rule in rules:
            # クールダウンチェック
            if self._is_in_cooldown(rule):
                continue

            if rule.condition_type == "score_threshold":
                alerts_generated += self._eval_score_threshold(rule)
            elif rule.condition_type == "score_change":
                alerts_generated += self._eval_score_change(rule)
            elif rule.condition_type == "new_hit":
                alerts_generated += self._eval_new_hit(rule)
            elif rule.condition_type == "data_quality":
                alerts_generated += self._eval_data_quality(rule)

        self.session.commit()
        return alerts_generated

    def _is_in_cooldown(self, rule):
        last_alert = self.session.query(AlertHistory).filter(
            AlertHistory.rule_id == rule.id
        ).order_by(AlertHistory.triggered_at.desc()).first()

        if last_alert:
            cooldown_end = last_alert.triggered_at + timedelta(minutes=rule.cooldown_minutes)
            return datetime.utcnow() < cooldown_end
        return False

    def _eval_score_threshold(self, rule):
        # hit_score が閾値を超えた広告を検出
        ...

    def _eval_new_hit(self, rule):
        # 新たにHIT判定された広告を検出
        ...

    def _eval_data_quality(self, rule):
        # NULL率が閾値を超えた場合にアラート
        ...

    def _create_alert(self, rule, ad_id, title, message, old_val=None, new_val=None, severity="info"):
        alert = AlertHistory(
            rule_id=rule.id,
            ad_id=ad_id,
            alert_type=rule.condition_type,
            severity=severity,
            title=title,
            message=message,
            old_value=old_val,
            new_value=new_val,
        )
        self.session.add(alert)
        return 1
```

### 4. DataFreshness サービス
```python
# backend/app/services/data_freshness.py
class DataFreshnessService:
    def __init__(self, session):
        self.session = session

    def compute_freshness_scores(self):
        """各広告の鮮度スコアを計算"""
        # last_crawled_at からの経過日数 → 鮮度スコア (0-100)
        # 1日以内: 100, 3日: 80, 7日: 60, 14日: 40, 30日: 20, 30日超: 0
        ...

    def generate_daily_report(self):
        """日次データ品質レポート生成"""
        # 全体の充填率, NULL率, 鮮度スコア平均を集計
        ...

    def schedule_auto_recrawl(self):
        """鮮度スコアが低い広告を自動再クロール対象に設定"""
        # freshness_score < 30 → ad_metadata["auto_recrawl_scheduled"] = True
        # Agent D が読んでクロール実行
        ...
```

## マイグレーション
```bash
# models を作成後、alembic でマイグレーション
cd C:/Users/ishit/ads_library/backend
alembic revision --autogenerate -m "add alert_rules and alert_history tables"
alembic upgrade head
```

## 完了条件
- [x] AlertRule / AlertHistory モデルが作成され、テーブルが存在
- [x] AlertEngine.evaluate_all_rules() が動作
- [x] 少なくとも3種のデフォルトルールが登録済み:
  - score_threshold: hit_score > 80 → "新しい大HIT候補"
  - new_hit: 新HIT検出 → "HIT広告発見"
  - data_quality: NULL率 > 10% → "データ品質警告"
- [x] COORDINATION_LOG に記載: C39 で API 化を依頼
- [x] status.md に記録
