# マイグレーション戦略視点 — DBスキーマの安全な進化

## なぜマイグレーション管理が重要か

- 本番DBにデータがある → スキーマ変更でデータ消失のリスク
- 複数エージェントが同時にモデル変更 → マイグレーション衝突
- Alembic のhead が複数できると解決が面倒
- ロールバック手順がないと障害時に詰む

---

## 現在のマイグレーション状態

### 確認コマンド

```bash
cd C:/Users/ishit/ads_library/backend

# 現在のhead
alembic heads

# 履歴
alembic history --verbose

# 現在のDB バージョン
alembic current

# 未適用のマイグレーション
alembic check
```

### 既知の問題

```
1. マイグレーション作成は Agent A (Planner 1) のみ
   → 他エージェントがモデル変更 → マイグレーション未作成 → DB不整合

2. ad_metadata (JSONB) はマイグレーション不要
   → スキーマレスのため、フィールド追加は自由
   → しかし、どのフィールドが存在するか管理されていない

3. 本番DBとローカルDBのスキーマが一致していない可能性
```

---

## マイグレーション作成ルール

### 命名規則

```
ファイル名: YYYYMMDD_HHMM_description.py
例:
  20250301_1200_add_notifications_table.py
  20250302_0900_add_tenant_id_to_ads.py
  20250303_1500_add_index_on_hit_score.py

理由:
  - 時刻ベースで衝突を避ける
  - descriptionで内容が一目で分かる
```

### コマンド

```bash
# 自動生成（モデルとDBの差分）
alembic revision --autogenerate -m "add_notifications_table"

# 手動作成（複雑な変更）
alembic revision -m "migrate_json_to_table"
```

---

## 安全なマイグレーションパターン

### パターン1: カラム追加（安全）

```python
def upgrade():
    op.add_column('ads', sa.Column('tenant_id', sa.UUID(), nullable=True))

def downgrade():
    op.drop_column('ads', 'tenant_id')
```

### パターン2: NOT NULL 追加（段階的）

```python
# Step 1: nullable=True で追加
def upgrade():
    op.add_column('ads', sa.Column('status', sa.String(20), nullable=True))

# Step 2: デフォルト値を設定（別マイグレーション）
def upgrade():
    op.execute("UPDATE ads SET status = 'active' WHERE status IS NULL")

# Step 3: NOT NULL 制約追加（別マイグレーション）
def upgrade():
    op.alter_column('ads', 'status', nullable=False)
```

### パターン3: カラム名変更（危険）

```python
# ❌ 直接リネーム → ダウンタイム
def upgrade():
    op.alter_column('ads', 'old_name', new_column_name='new_name')

# ✅ 段階的移行
# Step 1: 新カラム追加 + データコピー
def upgrade():
    op.add_column('ads', sa.Column('new_name', ...))
    op.execute("UPDATE ads SET new_name = old_name")

# Step 2: コードを新カラムに切り替え（デプロイ）

# Step 3: 旧カラム削除
def upgrade():
    op.drop_column('ads', 'old_name')
```

### パターン4: テーブル追加（安全）

```python
def upgrade():
    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text()),
        sa.Column('read', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_notifications_unread', 'notifications', ['read'])

def downgrade():
    op.drop_index('idx_notifications_unread')
    op.drop_table('notifications')
```

### パターン5: インデックス追加（注意）

```python
# 大きなテーブルではCONCURRENTLYを使う
def upgrade():
    # PostgreSQL の CREATE INDEX CONCURRENTLY はトランザクション外で実行
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_ads_category
        ON ads (category)
    """)

def downgrade():
    op.drop_index('idx_ads_category')

# 注意: CONCURRENTLY は Alembic のトランザクション内では使えない
# alembic.ini で transaction_per_migration = false に設定
```

### パターン6: JSONB フィールドのマイグレーション

```python
# ad_metadata の特定フィールドを専用カラムに昇格

def upgrade():
    # 1. 新カラム追加
    op.add_column('ads', sa.Column('is_still_running', sa.Boolean()))

    # 2. JSONB からデータ移行
    op.execute("""
        UPDATE ads
        SET is_still_running = (ad_metadata->>'is_still_running')::boolean
        WHERE ad_metadata->>'is_still_running' IS NOT NULL
    """)

def downgrade():
    # データをJSONBに戻す
    op.execute("""
        UPDATE ads
        SET ad_metadata = jsonb_set(
            COALESCE(ad_metadata, '{}'),
            '{is_still_running}',
            to_jsonb(is_still_running)
        )
        WHERE is_still_running IS NOT NULL
    """)
    op.drop_column('ads', 'is_still_running')
```

---

## ad_metadata (JSONB) フィールド管理

### 既知のフィールド一覧（README + コードから推定）

```
Agent A が管理:
  ad_archive_id         → Meta APIのID
  delivery_start        → 配信開始日
  delivery_end          → 配信終了日（配信中はNULL）
  is_still_running      → 配信中フラグ
  last_survival_check   → 最終生存チェック日
  impressions_lower     → インプレッション下限
  impressions_upper     → インプレッション上限
  spend_lower           → 消化額下限
  spend_upper           → 消化額上限
  publisher_platforms   → プラットフォーム一覧

Agent D が管理:
  snapshot_url          → Meta スナップショットURL
  video_url             → 動画URL
  image_url             → 画像URL
  thumbnail_url         → サムネイルURL
  media_type            → video / image / carousel
  media_extracted_at    → メディア抽出日時
  media_extraction_error → 抽出エラー

Agent C が管理:
  latest_hit_score      → 最新ヒットスコア
  hit_level             → HIT / 大HIT / RISING
  score_details         → スコア内訳
  trend_velocity        → トレンド速度
  estimated_daily_spend → 推定日別消化額

共有/その他:
  bylines               → 広告主名
  demographic_distribution → デモグラフィック
  delivery_by_region    → 地域別配信
  languages             → 言語
  page_id               → Facebookページ ID
  ad_creative_bodies    → 広告テキスト
  ad_creative_link_titles → リンクタイトル
```

### JSONB フィールド管理ファイル

```python
# app/models/ad_metadata_schema.py
# JSDNBの仕様書（実際のバリデーションではなくドキュメント）

AD_METADATA_FIELDS = {
    # Agent A
    "delivery_start": {"type": "date", "owner": "agent_a", "required": False},
    "delivery_end": {"type": "date", "owner": "agent_a", "required": False},
    "is_still_running": {"type": "bool", "owner": "agent_a", "required": False},
    "impressions_lower": {"type": "int", "owner": "agent_a", "required": False},
    "impressions_upper": {"type": "int", "owner": "agent_a", "required": False},
    "spend_lower": {"type": "float", "owner": "agent_a", "required": False},
    "spend_upper": {"type": "float", "owner": "agent_a", "required": False},

    # Agent D
    "video_url": {"type": "str", "owner": "agent_d", "required": False},
    "image_url": {"type": "str", "owner": "agent_d", "required": False},
    "thumbnail_url": {"type": "str", "owner": "agent_d", "required": False},
    "media_type": {"type": "str", "owner": "agent_d", "required": False},
    "media_extracted_at": {"type": "datetime", "owner": "agent_d", "required": False},

    # Agent C
    "latest_hit_score": {"type": "float", "owner": "agent_c", "required": False},
    "hit_level": {"type": "str", "owner": "agent_c", "required": False},
    "score_details": {"type": "dict", "owner": "agent_c", "required": False},
}
```

---

## 本番デプロイ手順

### マイグレーション適用フロー

```
1. ローカルでテスト
   alembic upgrade head
   → テストデータで確認
   → alembic downgrade -1 でロールバック確認

2. ステージング環境（なければ本番の手前で）
   → 本番DBのスナップショットから復元
   → マイグレーション適用
   → API動作確認

3. 本番適用
   → RDS スナップショット取得（バックアップ）
   → メンテナンスモード ON（可能なら）
   → alembic upgrade head
   → API動作確認
   → メンテナンスモード OFF

4. 問題発生時
   → alembic downgrade -1
   → or スナップショットから復旧
```

### Lambda からの自動マイグレーション

```python
# 危険: Lambda 起動時に自動マイグレーションは避ける
# 理由: 複数Lambda同時起動で衝突、ロールバック不可能

# 代わりに: 手動 or CI/CD で実行
# GitHub Actions:
#   - name: Run migrations
#     run: |
#       alembic upgrade head
```

---

## 衝突防止ルール

```
1. マイグレーション作成は Planner 1 (Agent A) のみ
2. 他エージェントはモデル変更を COORDINATION_LOG.md で通知
3. Agent A がまとめてマイグレーション作成
4. alembic heads で複数head がないか確認
5. 複数head がある場合: alembic merge で統合

# head 統合コマンド
alembic merge heads -m "merge_multiple_heads"
```

---

## 実装優先度

```
[Phase 1: 現状安定化]
  1. 現在のマイグレーション状態確認
  2. 本番DBとモデルの差分確認
  3. ad_metadata_schema.py 作成（ドキュメント）

[Phase 2: プロセス整備]
  4. マイグレーション命名規則の徹底
  5. downgrade の必須化
  6. CI/CD でのマイグレーションテスト

[Phase 3: 高度な管理]
  7. ステージング環境でのマイグレーションテスト自動化
  8. マイグレーションのパフォーマンステスト
  9. JSONB → 専用カラムの段階的移行
```
