# A38: データ鮮度自動管理パイプライン

## 概要
広告データの「鮮度」を自動管理し、古いデータの再クロール・欠損データの補完を
自律的に実行するパイプラインを構築する。

## 背景
現在58件の広告データしかなく、データの鮮度管理が手動。
プロダクトが「常に最新の広告市場を反映している」状態を自動で維持する仕組みが必要。

## タスク

### Task 1: データ鮮度スコアリング
```python
# backend/app/services/data_freshness.py (新規作成)

class DataFreshnessManager:
    """各広告のデータ鮮度をスコアリングし、再クロール優先度を決定する"""

    # 鮮度スコア = (データ完全性 × 0.3) + (時間的鮮度 × 0.4) + (メディア完全性 × 0.3)

    def compute_freshness_score(self, ad) -> float:
        """0.0 (完全に古い) ~ 1.0 (完全に新鮮)"""
        data_completeness = self._score_data_completeness(ad)
        time_freshness = self._score_time_freshness(ad)
        media_completeness = self._score_media_completeness(ad)
        return data_completeness * 0.3 + time_freshness * 0.4 + media_completeness * 0.3

    def _score_data_completeness(self, ad) -> float:
        """必須フィールドの充足率"""
        required = ['title', 'advertiser_name', 'genre', 'destination_url',
                     'creative_type', 'description']
        filled = sum(1 for f in required if getattr(ad, f, None))
        return filled / len(required)

    def _score_time_freshness(self, ad) -> float:
        """最終更新からの経過時間"""
        # 24h以内 = 1.0, 7日 = 0.7, 30日 = 0.3, 90日以上 = 0.0
        pass

    def _score_media_completeness(self, ad) -> float:
        """メディアURL・S3キーの充足率"""
        # thumbnail + image + video(動画の場合) + s3_key
        pass

    def get_stale_ads(self, session, threshold=0.5, limit=50) -> list:
        """鮮度スコアが閾値以下の広告を取得"""
        pass

    def get_incomplete_ads(self, session, limit=50) -> list:
        """必須データが欠損している広告を取得"""
        pass
```

### Task 2: 日次データ品質レポート
```python
# backend/app/services/data_quality_report.py (新規作成)

class DataQualityReporter:
    """毎日のデータ品質サマリーを生成する"""

    def generate_daily_report(self, session) -> dict:
        return {
            "total_ads": ...,
            "ads_by_freshness": {
                "fresh": ...,    # score >= 0.8
                "moderate": ..., # 0.5 <= score < 0.8
                "stale": ...,   # score < 0.5
            },
            "missing_fields": {
                "no_genre": ...,
                "no_destination_url": ...,
                "no_media": ...,
                "no_analysis": ...,
            },
            "media_status": {
                "completed": ...,
                "pending": ...,
                "failed": ...,
            },
            "recommendations": [
                # "23件の広告でジャンルが未分類です",
                # "15件の広告でメディア抽出が失敗しています",
            ]
        }
```

### Task 3: 自動再クロール・補完タスク
- `backend/app/tasks/freshness_tasks.py` (新規作成)
- EventBridge で毎日 AM 6:00 JST に実行
- 鮮度スコアが低い広告を優先して再クロール依頼をSQSに投入
- 欠損データの補完スクリプトを自動実行

### Task 4: ad_metadata に鮮度メタデータを記録
```python
meta["freshness_score"] = 0.85
meta["freshness_computed_at"] = "2026-03-01T10:00:00"
meta["auto_recrawl_scheduled"] = True
meta["data_quality_issues"] = ["missing_genre", "stale_media"]
```

## 完了条件
- [x] DataFreshnessManager が鮮度スコアを計算できる
- [x] DataQualityReporter が日次レポートを生成できる
- [x] 自動再クロールタスクが動作する
- [x] ad_metadata に鮮度情報が記録される

## 触っていいファイル
- backend/app/services/data_freshness.py (新規)
- backend/app/services/data_quality_report.py (新規)
- backend/app/tasks/freshness_tasks.py (新規)
- backend/app/models/ad.py (フィールド追加のみ)
- terraform/eventbridge.tf (Agent D と調整)

## 注意
- クロール実行自体は Agent D の領域。SQSにメッセージを投入するところまでが Agent A の責任。
- EventBridge の変更は COORDINATION_LOG.md で Agent D と調整。
