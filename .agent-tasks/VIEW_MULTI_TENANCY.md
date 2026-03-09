# マルチテナンシー視点 — 複数チーム/顧客への対応設計

## なぜ考える必要があるか

- 現在: 1ユーザー/1チーム前提で構築されている
- 将来: SaaS化した場合、複数の広告代理店/事業会社が使う
- サイドバーに「チームスペース」が既にある（未完成）
- 早期にデータ分離を考えないと、後からの改修コストが巨大

---

## 現在のデータ構造（シングルテナント）

```
ads テーブル
  ├── id
  ├── ad_archive_id  (Meta固有ID)
  ├── title
  ├── category
  ├── ad_metadata (JSONB)
  └── ... (全ユーザーが全データを見る)

product_rankings テーブル
  ├── ad_id
  ├── hit_score
  └── ... (グローバルランキング)

collections テーブル (JSON file)
  └── ... (誰のコレクションか不明)
```

### 問題点
- テナントID（team_id / org_id）がどこにもない
- 全データが全ユーザーに見える
- コレクション/ブックマークが共有されてしまう

---

## テナント分離モデル

### モデル比較

| モデル | データ分離 | コスト | 複雑度 | 推奨 |
|--------|----------|--------|--------|------|
| 共有DB + Row Level | 行レベル | 低 | 中 | ✅ Phase 1 |
| 共有DB + Schema分離 | スキーマ | 中 | 中 | Phase 2 |
| DB分離 | 完全 | 高 | 高 | 大規模のみ |

### 推奨: Row Level Security (RLS)

```sql
-- テナントIDを全テーブルに追加
ALTER TABLE ads ADD COLUMN tenant_id UUID;
ALTER TABLE product_rankings ADD COLUMN tenant_id UUID;
ALTER TABLE collections ADD COLUMN tenant_id UUID;
ALTER TABLE saved_searches ADD COLUMN tenant_id UUID;
ALTER TABLE api_keys ADD COLUMN tenant_id UUID;

-- インデックス
CREATE INDEX idx_ads_tenant ON ads (tenant_id);
CREATE INDEX idx_rankings_tenant ON product_rankings (tenant_id);

-- Row Level Security
ALTER TABLE ads ENABLE ROW LEVEL SECURITY;
CREATE POLICY ads_tenant_isolation ON ads
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## テナント管理

### テナントテーブル

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,  -- URL用
    plan VARCHAR(50) DEFAULT 'free',    -- free/pro/enterprise
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE tenant_members (
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'member',  -- owner/admin/member/viewer
    invited_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (tenant_id, user_id)
);
```

### テナントの設定

```json
{
  "max_ads": 10000,
  "max_crawls_per_day": 50,
  "max_members": 5,
  "features": {
    "ai_generation": true,
    "lp_analysis": true,
    "export": true,
    "api_access": false
  },
  "meta_token_encrypted": "...",
  "preferred_genres": ["美容", "健康食品"],
  "preferred_platforms": ["facebook", "instagram"]
}
```

---

## データ共有モデル

### 広告データの共有レベル

```
Level 1: 完全プライベート
  → テナントがクロールしたデータはそのテナントのみ
  → 小規模、コスト低い

Level 2: 公開データ + プライベート分析
  → Meta Ad Library のデータは全テナント共有
  → スコア/コレクション/メモはテナント固有
  → 中規模、コスト効率的 ← 推奨

Level 3: 完全共有 + アクセス制御
  → 全データ共有、閲覧権限で制御
  → 大規模、管理複雑
```

### Level 2 の実装

```sql
-- 広告データは共有（tenant_id = NULL で全テナント共通）
-- ランキング/スコアはテナント固有

ads テーブル:
  tenant_id = NULL → 共有データ（Meta APIから取得）
  tenant_id = UUID → テナント固有（手動登録など）

product_rankings テーブル:
  tenant_id = UUID → テナントごとにスコア計算
  → 同じ広告でもテナントによってスコアが異なる
  → テナントの業種/基準でスコア重み付けが変わる

collections テーブル:
  tenant_id = UUID → テナント固有のコレクション

notes テーブル (新規):
  tenant_id = UUID → テナント固有のメモ
  ad_id = UUID → 対象広告
```

---

## APIの変更

### テナントコンテキストの注入

```python
# app/middleware/tenant.py

async def tenant_middleware(request: Request, call_next):
    # JWTからテナントID取得
    token = request.headers.get("Authorization")
    if token:
        payload = decode_jwt(token)
        tenant_id = payload.get("tenant_id")
        request.state.tenant_id = tenant_id

        # DB セッションにテナントコンテキスト設定
        db = get_db()
        db.execute(text(f"SET app.current_tenant = '{tenant_id}'"))

    response = await call_next(request)
    return response
```

### エンドポイントの変更

```python
# 現在
@router.get("/rankings/pro-ranking")
async def pro_ranking(db: Session):
    return db.query(ProductRanking).all()  # 全データ

# マルチテナント後
@router.get("/rankings/pro-ranking")
async def pro_ranking(
    db: Session,
    tenant: Tenant = Depends(get_current_tenant)
):
    return db.query(ProductRanking)\
        .filter(ProductRanking.tenant_id == tenant.id)\
        .all()  # テナントのデータのみ
```

---

## プラン別機能制限

### 料金プラン設計

```
Free プラン:
  - 広告閲覧: 100件/月
  - クロール: 5回/月
  - メンバー: 1人
  - エクスポート: なし
  - AI生成: なし

Pro プラン:
  - 広告閲覧: 無制限
  - クロール: 50回/月
  - メンバー: 5人
  - エクスポート: CSV/Excel
  - AI生成: 100回/月

Enterprise プラン:
  - 全機能無制限
  - API アクセス
  - カスタムスコアリング
  - 専用サポート
  - SSO
```

### 使用量トラッキング

```sql
CREATE TABLE usage_tracking (
    tenant_id UUID REFERENCES tenants(id),
    period VARCHAR(7) NOT NULL,  -- "2025-03"
    metric VARCHAR(50) NOT NULL, -- "crawl_count", "ai_generation_count"
    value INTEGER DEFAULT 0,
    PRIMARY KEY (tenant_id, period, metric)
);

-- 使用量チェック
SELECT value FROM usage_tracking
WHERE tenant_id = $1 AND period = '2025-03' AND metric = 'crawl_count';
-- → プランの上限と比較
```

---

## マイグレーション計画

### Phase 1: テナント基盤（破壊的変更なし）

```
1. tenants テーブル作成
2. デフォルトテナント作成（既存データ用）
3. 全テーブルに tenant_id カラム追加（NULL許可）
4. 既存データにデフォルトテナントID設定
5. APIにテナントフィルタ追加（後方互換）
```

### Phase 2: 認証統合

```
1. JWT にテナントID追加
2. テナント切り替えUI
3. メンバー招待機能
4. ロールベースアクセス制御
```

### Phase 3: テナント分離完了

```
1. tenant_id を NOT NULL に変更
2. RLS ポリシー有効化
3. プラン別機能制限
4. 使用量トラッキング
5. 請求システム統合
```

---

## チームスペースUI（既存の未完成機能）

### サイドバーに既にある項目
```
チームスペース → 未完成
```

### 完成イメージ
```
┌─────────────────────┐
│ 🏢 チーム: ACME Inc │ ← テナント切り替え
├─────────────────────┤
│ 👥 メンバー (3)      │
│   ishit (オーナー)    │
│   user2 (管理者)      │
│   user3 (メンバー)    │
├─────────────────────┤
│ 📊 使用状況          │
│   クロール: 23/50     │
│   AI生成: 45/100      │
├─────────────────────┤
│ ⚙️ チーム設定        │
│   一般設定            │
│   メンバー管理        │
│   APIキー管理         │
│   プラン変更          │
└─────────────────────┘
```

---

## セキュリティ考慮

```
必須:
  - テナント間のデータ漏洩防止（RLS + アプリ層の二重チェック）
  - テナントAのAPIキーでテナントBのデータアクセス不可
  - 管理者がメンバーの権限を即時剥奪可能

推奨:
  - テナントごとのAPIキー暗号化（KMS）
  - 監査ログ（誰が何をいつ）
  - IP制限（Enterprise）
```
