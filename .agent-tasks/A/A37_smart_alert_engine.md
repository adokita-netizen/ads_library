# A37: スマートアラートエンジン

## 概要
ユーザーが設定した条件に基づき、新しいヒット広告やトレンド変化をリアルタイムで検知する
バックエンドのアラート判定ロジックを構築する。

## 背景
現在のVAAPは「見に行く」ツール。ユーザーが毎日ログインしないと変化に気づけない。
プロダクトの価値を「待っていれば教えてくれる」に変えることで、DAU/リテンションが劇的に改善する。

## タスク

### Task 1: アラートルール定義テーブル
```python
# backend/app/models/alert_rule.py (新規作成)

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)        # "美容ジャンルの新HIT"
    rule_type = Column(String(50), nullable=False)     # new_hit, trend_spike, competitor_new, score_change
    conditions = Column(JSON, nullable=False)           # {"genre": "美容", "min_score": 70}
    notification_channels = Column(JSON, default=[])    # ["in_app", "email", "slack"]
    is_active = Column(Boolean, default=True)
    cooldown_minutes = Column(Integer, default=60)      # 同一ルールの再通知間隔
    last_triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### Task 2: アラート履歴テーブル
```python
# backend/app/models/alert_history.py (新規作成)

class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    alert_type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)         # "新しいHIT広告: 美容液X"
    body = Column(Text, nullable=True)                  # 詳細テキスト
    data = Column(JSON, nullable=True)                  # {"ad_id": 123, "score": 85}
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
```

### Task 3: アラート評価エンジン
```python
# backend/app/services/alert_engine.py (新規作成)

class AlertEngine:
    """クロールやスコアリング完了後に呼ばれ、全アクティブルールを評価する"""

    def evaluate_all_rules(self, session, event_type: str, event_data: dict):
        """
        event_type: "crawl_completed", "score_updated", "new_ad_found"
        event_data: {"ad_ids": [...], "genre": "...", ...}
        """
        # 1. アクティブなルールを取得
        # 2. event_type に対応するルールをフィルタ
        # 3. conditions を評価
        # 4. マッチしたらAlertHistory作成
        # 5. cooldown チェック（last_triggered_at + cooldown_minutes < now）
        pass

    def _evaluate_new_hit(self, rule, event_data) -> list[dict]:
        """新HIT検知: スコアがmin_score以上 & ジャンルマッチ"""
        pass

    def _evaluate_trend_spike(self, rule, event_data) -> list[dict]:
        """トレンド急上昇: 前日比でview_count_increaseがN%以上"""
        pass

    def _evaluate_competitor_new(self, rule, event_data) -> list[dict]:
        """競合新広告: 指定広告主の新しい広告を検知"""
        pass

    def _evaluate_score_change(self, rule, event_data) -> list[dict]:
        """スコア変動: 指定広告のスコアがN点以上変動"""
        pass
```

### Task 4: ランキング計算後のアラートトリガー統合
- `backend/app/tasks/ranking_tasks.py` の `compute_rankings` 完了後に `AlertEngine.evaluate_all_rules()` を呼ぶ
- `backend/app/tasks/crawl_tasks.py` のクロール完了後にも呼ぶ
- 非同期で実行（メイン処理をブロックしない）

## 完了条件
- [x] alert_rules / alert_history テーブルが作成されている
- [x] AlertEngine が4種類のルールを評価できる
- [x] ランキング計算後・クロール後にアラートが発火する
- [x] AlertHistory にレコードが保存される
- [x] Alembic マイグレーション作成済み

## 触っていいファイル
- backend/app/models/alert_rule.py (新規)
- backend/app/models/alert_history.py (新規)
- backend/app/services/alert_engine.py (新規)
- backend/app/tasks/ranking_tasks.py (トリガー追加のみ)
- migrations/ (Alembic)

## 注意
- crawl_tasks.py は Agent D の専有領域。トリガー追加は COORDINATION_LOG.md 経由で依頼すること。
- フロントエンドの通知UIは Agent B (B42) が担当。
