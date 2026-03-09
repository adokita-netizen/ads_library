# Round 2 テスト計画

## 1. Agent A テスト

### A-R2-1: データ品質修正
```bash
cd C:/Users/ishit/ads_library/backend

# テスト1: NULL率チェック（修正前）
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import func
s = SyncSessionLocal()
total = s.query(func.count(Ad.id)).scalar()
for col in ['title','category','destination_url','platform','advertiser_name','creative_type']:
    null = s.query(func.count(Ad.id)).filter(getattr(Ad, col) == None).scalar()
    print(f'{col}: {null}/{total} NULL ({round(null/total*100,1)}%)')
s.close()
"

# テスト2: 修正後の同じチェック（全項目 5%未満が合格）
```

### A-R2-2: デルタ計算
```bash
# テスト1: デルタフィールド存在確認
python -c "
from app.models.ad_metrics import AdDailyMetrics
print(hasattr(AdDailyMetrics, 'view_count_increase'))
print(hasattr(AdDailyMetrics, 'spend_increase'))
"

# テスト2: デルタ値が正の値
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad_metrics import AdDailyMetrics
from sqlalchemy import func
s = SyncSessionLocal()
total = s.query(func.count(AdDailyMetrics.id)).scalar()
has_delta = s.query(func.count(AdDailyMetrics.id)).filter(
    AdDailyMetrics.view_count_increase != None,
    AdDailyMetrics.view_count_increase > 0
).scalar()
print(f'Records with delta: {has_delta}/{total}')
s.close()
"
```

### A-R2-4: DBリトライ
```bash
# テスト: get_session_with_retry が存在し呼び出し可能
python -c "
from app.core.database import get_session_with_retry
session = get_session_with_retry()
result = session.execute('SELECT 1').scalar()
assert result == 1
print('DB retry: OK')
session.close()
"
```

### A-R2-5: メタデータバリデーション
```bash
# テスト: バリデーションスクリプト実行
python -m scripts.validate_metadata
# 終了コード 0 = 全必須キー存在, 1 = 警告あり
echo "Exit code: $?"
```

---

## 2. Agent B テスト

### B-R2-1: ダークモード
```bash
cd C:/Users/ishit/ads_library/frontend

# テスト1: ビルド成功
npx next build --no-lint

# テスト2: dark: クラスの存在確認
grep -r "dark:" src/components/common/Sidebar.tsx | head -5
grep -r "dark:" src/components/dashboard/ProRankingView.tsx | head -5
grep -r "dark:" src/components/dashboard/ProRankingTable.tsx | head -5

# テスト3: useTheme フック存在
test -f src/hooks/useTheme.ts && echo "useTheme: EXISTS" || echo "useTheme: MISSING"

# テスト4: ThemeToggle コンポーネント存在
test -f src/components/common/ThemeToggle.tsx && echo "ThemeToggle: EXISTS" || echo "ThemeToggle: MISSING"

# テスト5: tailwind.config.js に darkMode 設定
grep "darkMode" tailwind.config.js
```

### B-R2-3: テーブルUX
```bash
# テスト1: sticky header クラス存在
grep -c "sticky" src/components/dashboard/ProRankingTable.tsx

# テスト2: localStorage カラム保存
grep -c "localStorage" src/components/dashboard/ProRankingTable.tsx

# テスト3: URL同期（useSearchParams）
grep -c "useSearchParams\|searchParams" src/components/dashboard/ProRankingTable.tsx
```

### 全体ビルドテスト
```bash
# First Load JS サイズ確認
npx next build --no-lint 2>&1 | grep "First Load JS"
# 合格基準: 160kB 以下
```

---

## 3. Agent C テスト

### C-R2-1: AI Chat API
```bash
cd C:/Users/ishit/ads_library/backend

# バックエンドを起動してから実行
# uvicorn app.main:app --reload --port 8000

# テスト1: 新規会話 + メッセージ送信
curl -s -X POST http://localhost:8000/api/v1/ai-chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the total ads in the database?"}' | python -m json.tool

# テスト2: 会話一覧
curl -s http://localhost:8000/api/v1/ai-chat/conversations | python -m json.tool

# テスト3: ジャンル分析インテント
curl -s -X POST http://localhost:8000/api/v1/ai-chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "美容ジャンルのHIT広告の共通点は？"}' | python -m json.tool

# テスト4: 会話削除
curl -s -X DELETE http://localhost:8000/api/v1/ai-chat/conversations/1
```

### C-R2-2: 通知API
```bash
# テスト1: 通知一覧（初期は空）
curl -s "http://localhost:8000/api/v1/rankings/notifications" | python -m json.tool

# テスト2: アラートルール作成
curl -s -X POST http://localhost:8000/api/v1/rankings/alert-rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Score Alert",
    "condition_type": "score_threshold",
    "target_field": "hit_score",
    "operator": "gt",
    "threshold": 80
  }' | python -m json.tool

# テスト3: ルール一覧
curl -s "http://localhost:8000/api/v1/rankings/alert-rules" | python -m json.tool

# テスト4: 全既読
curl -s -X PUT "http://localhost:8000/api/v1/rankings/notifications/read-all"
```

### C-R2-4: N+1解消
```bash
# テスト: SQL回数の計測（修正前後で比較）
# ログレベルをDEBUGにしてSQL出力を確認
LOG_LEVEL=DEBUG curl -s "http://localhost:8000/api/v1/rankings/pro-ranking?page=1&per_page=20" > /dev/null
# 合格基準: SQL回数が修正前の70%以下
```

### C-R2-5: ページング上限
```bash
# テスト1: 上限超過で400
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/rankings/pro-ranking?per_page=200"
# 期待: 400

# テスト2: 上限内で200
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/rankings/pro-ranking?per_page=50"
# 期待: 200

# テスト3: 負のページ番号で400
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/rankings/pro-ranking?page=-1"
# 期待: 400
```

---

## 4. Agent D テスト

### D-R2-1: 定期クロール
```bash
cd C:/Users/ishit/ads_library/backend

# テスト1: ジャンルローテーション
python -c "
from app.tasks.crawl_tasks import get_today_keywords
kws = get_today_keywords()
print(f'Today: {len(kws)} keywords')
for kw in kws: print(f'  - {kw}')
"

# テスト2: 重複ガード
python -c "
from app.tasks.crawl_tasks import is_duplicate_crawl
from app.core.database import SyncSessionLocal
s = SyncSessionLocal()
result = is_duplicate_crawl(s, 'test_keyword')
print(f'Duplicate check: {result}')
s.close()
"
```

### D-R2-2: 動画処理
```bash
# テスト1: ffprobe 利用可能確認
which ffprobe && echo "ffprobe: OK" || echo "ffprobe: NOT FOUND"

# テスト2: メタデータ抽出テスト（テスト動画がある場合）
python -c "
from app.tasks.media_tasks import extract_video_metadata
# result = extract_video_metadata('/tmp/test_video.mp4')
# print(result)
print('Test skipped (no test video)')
"
```

### D-R2-4: LPクローラ
```bash
# テスト: 1件のLPクロール
python -c "
import asyncio
from app.services.crawling.lp_crawler import LPCrawler
crawler = LPCrawler()
result = asyncio.run(crawler.crawl_lp('https://example.com', 0))
print(result)
"
```

---

## 5. 統合テスト

### E2E データフロー
```
1. D-R2-1 でクロール → 新規広告 N 件追加
2. A-R2-3 で分析パイプライン → category, title, days_running 埋まる
3. C (recompute_hit_scores) → hit_score 計算
4. B (ProRankingTable) → テーブルに新規広告が表示される
```

### 手動確認
```bash
# 全体の広告数
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import func
s = SyncSessionLocal()
print(f'Total ads: {s.query(func.count(Ad.id)).scalar()}')
s.close()
"

# PRO RANKING API レスポンス確認
curl -s "http://localhost:8000/api/v1/rankings/pro-ranking?page=1&per_page=5" | python -m json.tool | head -50
```
