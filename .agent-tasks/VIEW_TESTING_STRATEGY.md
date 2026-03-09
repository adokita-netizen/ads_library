# テスト戦略視点 — 何をどうテストすべきか

## 現状: テストがほぼ無い（推定）

- pytest, factory-boy, respx は requirements.txt にある
- tests/ ディレクトリの状態は未確認
- 14,779行の rankings.py にユニットテストが無いと推定

---

## テストピラミッド

```
         /\
        /  \          E2E テスト (少数)
       /    \         Playwright/Cypress でブラウザテスト
      /------\
     /        \       Integration テスト (中程度)
    /          \      API エンドポイントの結合テスト
   /------------\
  /              \    Unit テスト (多数)
 /                \   サービス・ユーティリティの単体テスト
/------------------\
```

### 今の優先度
E2E > Integration > Unit（通常と逆）

理由: コードは書かれているが「動くか分からない」状態。
まず「動く」ことを確認する E2E/Integration が最優先。

---

## Level 1: API スモークテスト（最優先）

### 目的: 全エンドポイントが500を返さないことを確認

```python
# tests/test_smoke.py
import pytest
import httpx

BASE = "http://localhost:8000/api/v1"

ENDPOINTS = [
    # Core
    ("GET", "/rankings/pro-ranking?page=1&per_page=5"),
    ("GET", "/rankings/dashboard-summary"),
    ("GET", "/rankings/genre-master"),
    ("GET", "/rankings/hit-ads?limit=5"),
    ("GET", "/rankings/smart-autocomplete?query=test"),
    ("GET", "/rankings/score-distribution"),
    ("GET", "/rankings/genre-comparison"),

    # Export
    ("GET", "/rankings/export/csv?genre=all"),
    ("GET", "/rankings/export/json?genre=all"),

    # Search
    ("GET", "/rankings/search-collections"),

    # Trends
    ("GET", "/rankings/trends/weekly"),

    # Health
    ("GET", "/../health"),
]

@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_no_500(method, path):
    """All endpoints should return non-500 status."""
    with httpx.Client(base_url=BASE, timeout=30) as client:
        if method == "GET":
            r = client.get(path)
        elif method == "POST":
            r = client.post(path, json={})

        assert r.status_code < 500, f"{method} {path} returned {r.status_code}: {r.text[:200]}"
```

### 実行
```bash
cd C:/Users/ishit/ads_library/backend
# バックエンド起動済みの状態で
pytest tests/test_smoke.py -v
```

---

## Level 2: API レスポンス形式テスト

### 目的: フロントエンドが期待するフィールドが返ることを確認

```python
# tests/test_response_format.py
import httpx

BASE = "http://localhost:8000/api/v1"

def test_pro_ranking_format():
    """pro-ranking should return items with required fields."""
    r = httpx.get(f"{BASE}/rankings/pro-ranking?page=1&per_page=5")
    assert r.status_code == 200
    data = r.json()

    assert "items" in data or isinstance(data, list)
    items = data.get("items", data)

    if items:
        item = items[0]
        required_fields = [
            "rank", "product_name", "advertiser_name",
            "genre", "hit_score", "hit_level",
        ]
        for field in required_fields:
            assert field in item, f"Missing field: {field}"

def test_dashboard_summary_format():
    """dashboard-summary should return KPI metrics."""
    r = httpx.get(f"{BASE}/rankings/dashboard-summary")
    assert r.status_code == 200
    data = r.json()

    required_fields = [
        "total_ads", "active_ads", "hit_count", "avg_score"
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

def test_genre_master_format():
    """genre-master should return categorized genres."""
    r = httpx.get(f"{BASE}/rankings/genre-master")
    assert r.status_code == 200
    data = r.json()

    # Should have groups or items
    assert "groups" in data or "items" in data or isinstance(data, list)

def test_autocomplete_format():
    """autocomplete should return suggestions."""
    r = httpx.get(f"{BASE}/rankings/smart-autocomplete?query=a")
    assert r.status_code == 200
    data = r.json()

    assert "suggestions" in data or isinstance(data, list)
```

---

## Level 3: データ整合性テスト

### 目的: DBのデータが論理的に正しいことを確認

```python
# tests/test_data_integrity.py
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import ProductRanking

def test_all_ads_have_rankings():
    """Every ad should have a corresponding ProductRanking."""
    s = SyncSessionLocal()
    ad_count = s.query(Ad).count()
    ranking_count = s.query(ProductRanking).count()
    s.close()

    assert ranking_count >= ad_count * 0.9, \
        f"Only {ranking_count}/{ad_count} ads have rankings"

def test_hit_scores_in_range():
    """All hit scores should be 0-100."""
    s = SyncSessionLocal()
    invalid = s.query(ProductRanking).filter(
        (ProductRanking.hit_score < 0) | (ProductRanking.hit_score > 100)
    ).count()
    s.close()

    assert invalid == 0, f"{invalid} rankings have score outside 0-100"

def test_categories_not_null():
    """Most ads should have a category."""
    s = SyncSessionLocal()
    total = s.query(Ad).count()
    with_category = s.query(Ad).filter(Ad.category != None).count()
    s.close()

    ratio = with_category / total if total > 0 else 0
    assert ratio >= 0.8, f"Only {ratio:.0%} of ads have category"

def test_no_orphan_rankings():
    """Every ProductRanking should reference a valid ad."""
    s = SyncSessionLocal()
    from sqlalchemy import not_
    orphans = s.query(ProductRanking).filter(
        not_(ProductRanking.ad_id.in_(s.query(Ad.id)))
    ).count()
    s.close()

    assert orphans == 0, f"{orphans} orphaned rankings found"
```

---

## Level 4: スコアリングロジックテスト

```python
# tests/test_scoring.py
from app.services.ranking.ranking_service import RankingService

def test_longevity_score():
    """Longer running ads should get higher scores."""
    svc = RankingService()

    assert svc._calc_longevity_score(3) < svc._calc_longevity_score(30)
    assert svc._calc_longevity_score(30) < svc._calc_longevity_score(90)
    assert svc._calc_longevity_score(0) == 0
    assert 0 <= svc._calc_longevity_score(365) <= 100

def test_hit_level_classification():
    """Hit levels should match score thresholds."""
    svc = RankingService()

    assert svc._classify_hit(80) == "mega_hit"
    assert svc._classify_hit(60) == "hit"
    assert svc._classify_hit(40) == "normal"
    assert svc._classify_hit(20) == "low"
```

---

## Level 5: フロントエンド テスト

### ビルドテスト（最低限）
```bash
cd C:/Users/ishit/ads_library/frontend
npx next build --no-lint
# exit code 0 = 成功
```

### コンポーネントテスト（将来）
```typescript
// __tests__/ProRankingTable.test.tsx
import { render, screen } from '@testing-library/react'
import ProRankingTable from '@/components/dashboard/ProRankingTable'

const mockData = {
  items: [{
    rank: 1,
    product_name: "テスト商品",
    hit_score: 75,
    hit_level: "hit",
  }],
  total: 1,
}

test('renders ranking table with data', () => {
  render(<ProRankingTable data={mockData} />)
  expect(screen.getByText('テスト商品')).toBeInTheDocument()
})
```

---

## CI/CD でのテスト実行

### GitHub Actions に追加
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  api-smoke:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: vaap_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements-lambda.txt
      - run: pip install pytest httpx
      - run: cd backend && pytest tests/test_smoke.py -v

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci
      - run: cd frontend && npx next build --no-lint
```

---

## テスト優先度

| レベル | 種類 | 件数目標 | 担当 | タイミング |
|--------|------|---------|------|-----------|
| 1 | APIスモーク | 20+ | Planner 2 | 今すぐ |
| 2 | レスポンス形式 | 10+ | Planner 2 | Day 1-2 |
| 3 | データ整合性 | 5+ | Planner 1 | Day 2-3 |
| 4 | スコアリング | 10+ | Planner 2 | Day 3-5 |
| 5 | フロントビルド | 1 | Planner 3 | 今すぐ |
