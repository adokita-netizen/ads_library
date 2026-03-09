# エージェント間コンフリクト履歴と予防 — 過去の衝突パターンから学ぶ

## なぜこの視点が必要か

4エージェント × 3プランナーが同時に動くと、ファイル所有権ルールを破る事故が起きる。
過去のパターンを知ることで予防する。

---

## コンフリクトが起きやすいポイント TOP 10

### 1. ad_metadata の同時書き込み
**リスク**: ★★★★★
**パターン**:
```python
# Agent A が実行中
meta = dict(ad.ad_metadata or {})
meta["is_still_running"] = True

# 同時に Agent C が実行
meta = dict(ad.ad_metadata or {})  # Agent A の変更を読んでいない
meta["latest_hit_score"] = 75

# Agent C が commit → Agent A の変更が消える
```

**予防**:
- エージェントは同じ広告を同時に更新しない
- Planner 1 (A+D) が先に全データ埋め → その後 Planner 2 (C) がスコア計算
- SELECT FOR UPDATE でロック（パフォーマンス注意）

### 2. backend/app/models/ad.py の同時変更
**リスク**: ★★★★☆
**パターン**: Agent A がフィールド追加、Agent C も別フィールド追加 → Git コンフリクト
**予防**:
- ad.py の変更は 1日1エージェントのみ
- フィールド追加は COORDINATION_LOG.md で事前通知

### 3. alembic マイグレーションの同時作成
**リスク**: ★★★★☆
**パターン**: 2エージェントが同時に `alembic revision --autogenerate` → 2つのhead
**予防**:
- マイグレーション作成は Agent A (Planner 1) のみが行う
- 他エージェントはモデル変更のみ、マイグレーションは依頼

### 4. requirements.txt の同時変更
**リスク**: ★★★☆☆
**パターン**: Agent D が playwright バージョン更新、Agent C が新パッケージ追加
**予防**:
- requirements.txt の変更は COORDINATION_LOG.md で通知
- 可能なら Planner 1 が一括管理

### 5. HitAdAnalysisView.tsx の肥大化
**リスク**: ★★★★☆（Agent B 内部問題）
**パターン**: 13回修正されて2000+行 → 新しい修正が既存機能を壊す
**予防**:
- 修正前に必ず `npx next build --no-lint` で現状確認
- 修正後にも同じコマンドで確認
- 可能なら分割してから修正

### 6. rankings.py と ranking_service.py の責務境界
**リスク**: ★★★☆☆
**パターン**: スコアロジックがrankings.pyにもranking_service.pyにもある → どっちが正？
**予防**:
- ビジネスロジックは ranking_service.py に集約
- rankings.py はHTTPハンドリングのみ

### 7. JSON ファイルの同時書き込み
**リスク**: ★★☆☆☆
**場所**: `backend/data/collections.json`, `backend/data/saved_searches.json`
**パターン**: 2つのAPIリクエストが同時にJSONファイルを書き込み → データ消失
**予防**:
- ファイルロック or DB移行

### 8. Docker イメージの不整合
**リスク**: ★★☆☆☆
**パターン**: Agent D が Dockerfile.worker を変更 → ECR にプッシュ前にAgent A がWorker実行
→ 古いイメージで実行される
**予防**:
- Dockerfile 変更後は必ずビルド + プッシュ
- COORDINATION_LOG.md で通知

### 9. 環境変数の不整合
**リスク**: ★★☆☆☆
**パターン**: Agent A が新しい環境変数を追加 → Lambda/ECS に設定されていない
→ 本番でKeyError
**予防**:
- 新しい環境変数は `os.getenv("KEY", "default")` でデフォルト値必須
- terraform の変数も同時に更新

### 10. フロントの型定義とバックエンドのスキーマ不整合
**リスク**: ★★★☆☆
**パターン**: Agent C がAPIレスポンスにフィールド追加 → Agent B のTypeScript型に反映されない
→ フロントで undefined エラー
**予防**:
- API変更時は COORDINATION_LOG.md に型情報も記載
- フロントはオプショナルチェーン `?.` で防御

---

## 安全な作業フロー

### エージェントの1タスクの流れ
```
1. COORDINATION_LOG.md を読む（他エージェントの最新状態確認）
2. 自分の status.md を「作業中」に更新
3. 対象ファイルの最新版を git pull
4. 変更前のテスト/ビルド確認
5. 変更を実装
6. 変更後のテスト/ビルド確認
7. git commit + push
8. status.md を「完了」に更新
9. COORDINATION_LOG.md に影響範囲を記載
```

### コンフリクト発生時の解決フロー
```
1. git pull でコンフリクト検出
2. コンフリクトファイルの所有権を確認（README.md のファイル専有マップ）
3. 所有権が自分 → 自分の変更を優先
4. 所有権が相手 → 相手の変更を優先
5. 両方が正当 → COORDINATION_LOG.md で協議
6. 解決後に git add + commit
7. テスト/ビルド確認
```

---

## ファイルロック表（同時編集禁止）

| ファイル | 現在ロック | ロック者 |
|---------|-----------|---------|
| backend/app/models/ad.py | 🔓 Agent A 優先 | Planner 1 |
| backend/app/api/endpoints/rankings.py | 🔓 Agent C 専有 | Planner 2 |
| frontend/src/components/dashboard/HitAdAnalysisView.tsx | 🔓 Agent B 専有 | Planner 3 |
| backend/requirements.txt | 🔓 Planner 1 管理 | Planner 1 |
| alembic/ | 🔓 Agent A のみ作成 | Planner 1 |
| terraform/ | 🔓 協議制 | 全Planner |
| docker/Dockerfile.worker | 🔓 Agent D 専有 | Planner 1 |

---

## 過去のコード品質改修ステータス（COORDINATION_LOG.md より）

### 完了した改修
- Agent D: 4/4 完了 (media_tasks, media_extraction, crawl_tasks, meta_crawler)
- Agent A: 3/5 完了 (database.py, config.py, lambda_handler.py)
- Agent C: 7/8 完了 (rankings.py, ads.py, media.py)

### 未完了（コンフリクトリスクあり）
- [ ] sqs_ecs_trigger.py: batchItemFailures — Agent A 担当だが影響が広い
- [ ] lambda.tf: ReportBatchItemFailures — Terraform変更、全体に影響
- [ ] ads.py: fetch_all_thumbnails — Agent C 担当
- [ ] Agent B: 全5件未着手 (ProductDetailModal, AdLibrary, HitAdAnalysisView, api.ts, types)
