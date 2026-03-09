# D-R2-1: Scheduled Crawl Setup (D7)
# 優先度: P0 | 前提: なし | ブロック: D-R2-3, A-R2-3

## 目的
ジャンル別ローテーションの定期クロールを本番稼働させる。
200+件の広告目標を達成する。

## 対象ファイル (全て Agent D 専有)
- `terraform/eventbridge.tf` (修正)
- `backend/app/services/crawling/meta_crawler.py` (確認)
- `backend/app/tasks/crawl_tasks.py` (修正)
- `backend/lambda_handler.py` (_run_crawl 関数末尾のみ)

## 実装

### Step 1: EventBridge スケジュール確認・追加
```hcl
# terraform/eventbridge.tf
# D27 で weekly_media_extraction は追加済み
# ジャンル別クロールスケジュールを追加

resource "aws_cloudwatch_event_rule" "daily_genre_crawl" {
  name                = "vaap-daily-genre-crawl"
  description         = "Daily genre rotation crawl"
  schedule_expression = "cron(0 19 ? * MON-FRI *)"  # 04:00 JST weekdays
}

# Lambda のイベントペイロードでジャンルを指定
resource "aws_cloudwatch_event_target" "daily_genre_crawl_target" {
  rule = aws_cloudwatch_event_rule.daily_genre_crawl.name
  arn  = aws_lambda_function.vaap_api.arn
  input = jsonencode({
    action = "crawl"
    rotate_genre = true
  })
}
```

### Step 2: ジャンルローテーション実装
```python
# crawl_tasks.py に追加

GENRE_ROTATION = {
    0: ["beauty", "cosmetics"],           # Monday
    1: ["health_food", "supplements"],      # Tuesday
    2: ["diet", "fitness"],                 # Wednesday
    3: ["hair_growth", "skincare"],         # Thursday
    4: None,                                # Friday = all genres (diff check)
}

GENRE_KEYWORDS = {
    "beauty": ["美容", "美白", "シミ", "シワ"],
    "cosmetics": ["コスメ", "化粧品", "ファンデーション"],
    "health_food": ["健康食品", "サプリ", "青汁"],
    "supplements": ["サプリメント", "ビタミン", "プロテイン"],
    "diet": ["ダイエット", "痩せる", "減量"],
    "fitness": ["筋トレ", "フィットネス", "ジム"],
    "hair_growth": ["育毛", "発毛", "薄毛"],
    "skincare": ["スキンケア", "保湿", "美肌"],
}

def get_today_keywords() -> list[str]:
    """今日の曜日に応じたキーワードリストを返す"""
    from datetime import datetime
    day = datetime.now().weekday()  # 0=Mon
    genres = GENRE_ROTATION.get(day)

    if genres is None:
        # Friday: all genres
        all_keywords = []
        for kws in GENRE_KEYWORDS.values():
            all_keywords.extend(kws)
        return all_keywords

    keywords = []
    for g in genres:
        keywords.extend(GENRE_KEYWORDS.get(g, []))
    return keywords
```

### Step 3: クロール重複ガード (CI-038)
```python
# crawl_tasks.py に追加

import hashlib
from datetime import datetime, timedelta

def is_duplicate_crawl(session, keyword: str, hours: int = 6) -> bool:
    """同一キーワードで直近N時間以内にクロール済みかチェック"""
    from app.models.ad import Ad  # or crawl_log table
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # crawl_log テーブルがあればそちらを使う
    # なければ ads テーブルの last_crawled_at で代替
    recent = session.execute(text("""
        SELECT COUNT(*) FROM ads
        WHERE ad_metadata->>'last_crawl_keyword' = :keyword
        AND updated_at > :cutoff
    """), {"keyword": keyword, "cutoff": cutoff}).scalar()

    return recent > 0
```

### Step 4: lambda_handler.py 連携 (_run_crawl 末尾のみ)
```python
# lambda_handler.py の _run_crawl() の最後に
# rotate_genre=True の場合、get_today_keywords() を使ってクロール

if event.get("rotate_genre"):
    keywords = get_today_keywords()
    for kw in keywords:
        if not is_duplicate_crawl(session, kw):
            crawl_result = crawl_with_keyword(kw, limit=20)
            logger.info(f"Crawled '{kw}': {crawl_result['count']} ads")
```

### Step 5: ローカルテスト
```bash
cd C:/Users/ishit/ads_library/backend

# ジャンルローテーション確認
python -c "
from app.tasks.crawl_tasks import get_today_keywords
keywords = get_today_keywords()
print(f'Today keywords: {keywords}')
"

# 1キーワードでテストクロール
python -c "
from app.services.crawling.meta_crawler import MetaCrawler
crawler = MetaCrawler()
result = crawler.search('beauty ad', limit=5)
print(f'Found: {len(result)} ads')
"
```

## 完了条件
- [ ] ジャンルローテーションロジックが実装済み
- [ ] EventBridge スケジュールが設定済み
- [ ] 重複クロールガードが動作する
- [ ] 1キーワードのテストクロールが成功
- [ ] 結果を status.md に記録
- [ ] COORDINATION_LOG: 新規クロールデータあり → Planner 1 (Agent A) に分析パイプライン実行依頼
