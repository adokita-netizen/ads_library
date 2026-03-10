# Agent Tasks — タスク管理ディレクトリ

## ★ 3 Planner 体制 (2026-03-01 開始) ★

```
Planner 1: DATA FOUNDATION    → Agent A + D → PLANNER1_DATA_FOUNDATION.md
Planner 2: API VERIFICATION   → Agent C     → PLANNER2_API_VERIFICATION.md
Planner 3: FRONTEND E2E       → Agent B     → PLANNER3_FRONTEND_E2E.md

連絡: COORDINATION_LOG.md (クロスプランナー通知)
戦略: PLANNER_STRATEGY.md (全体方針)
```

### 方針: コードは80%以上書かれている。新機能より「動かす」が最優先。

## 追加設計書
- `DPRO_PARITY_IMPLEMENTATION_SPEC.md`: 動画広告分析Pro差分埋め仕様
- `AWS_PERSISTENT_DATA_SYSTEM_DESIGN.md`: AWS連携で継続蓄積する運用設計
- `TASK_ASSIGNMENT_2026-03-10_CREATIVE_LP_RESUME.md`: creative / LP 完成度 100% resolved 到達時点の復帰メモ

## 構成
```
.agent-tasks/
├── README.md                     ← このファイル
├── PLANNER_STRATEGY.md           ← 全体戦略
├── PLANNER1_DATA_FOUNDATION.md   ← Planner 1 指示書
├── PLANNER2_API_VERIFICATION.md  ← Planner 2 指示書
├── PLANNER3_FRONTEND_E2E.md      ← Planner 3 指示書
├── CONTINUOUS_IMPROVEMENT_BACKLOG.md ← 継続改善タスク（常時追加）
├── COORDINATION_LOG.md           ← プランナー間連絡
├── A/                     ← Agent A: バックエンド・データ基盤
│   ├── INSTRUCTIONS.md
│   ├── A1〜A7             [済]
│   ├── A8〜A36            [Phase 1 — 基盤構築]
│   ├── A37〜A38           [Phase 2 — アラートエンジン/鮮度管理]
│   └── status.md
├── B/                     ← Agent B: フロントエンド
│   ├── INSTRUCTIONS.md
│   ├── B1〜B12, B19       [済/部分済]
│   ├── B13〜B40           [Phase 1 — 基盤構築]
│   ├── B41〜B44           [Phase 2 — オンボーディング/通知/AIチャット/カスタマイズ]
│   └── status.md
├── C/                     ← Agent C: バックエンド・スコアリング
│   ├── INSTRUCTIONS.md
│   ├── C1〜C9             [済]
│   ├── C10〜C37           [Phase 1 — 基盤構築]
│   ├── C38〜C40           [Phase 2 — AIチャットAPI/通知API/外部連携]
│   └── status.md
└── D/                     ← Agent D: メディア・クローリング
    ├── INSTRUCTIONS.md
    ├── D1〜D6             [済]
    ├── D7〜D32            [Phase 1 — 基盤構築]
    ├── D33〜D35           [Phase 2 — スマートクロール/動画分析/マルチPF]
    └── status.md
```

## コンフリクト防止: ファイル専有マップ

| 領域 | Agent A | Agent B | Agent C | Agent D |
|------|---------|---------|---------|---------|
| `backend/scripts/` (データ品質系) | **書込** | 禁止 | 禁止 | 禁止 |
| `backend/scripts/check_lp_health.py` | 禁止 | 禁止 | **書込** | 禁止 |
| `backend/scripts/recompute_hit_scores.py` | 禁止 | 禁止 | **書込** | 禁止 |
| `backend/scripts/` (メディア系: extract_missing_videos, backfill_media_urls, fix_bad_thumbnails, update_media_status, fix_creative_types) | 禁止 | 禁止 | 禁止 | **書込** |
| `backend/app/tasks/metrics_tasks.py` | **書込** | 禁止 | 禁止 | 禁止 |
| `backend/app/tasks/crawl_tasks.py` | 禁止 | 禁止 | 禁止 | **書込** |
| `backend/app/tasks/media_tasks.py` | 禁止 | 禁止 | 禁止 | **書込** |
| `backend/app/services/crawling/` | 禁止 | 禁止 | 禁止 | **書込** |
| `backend/app/services/media_extraction.py` | 禁止 | 禁止 | 禁止 | **書込** |
| `backend/app/services/thumbnail_fetcher.py` | 禁止 | 禁止 | 禁止 | **書込** |
| `backend/app/services/ranking/` | 禁止 | 禁止 | **書込** | 禁止 |
| `backend/app/services/competitive/` | 禁止 | 禁止 | **書込** | 禁止 |
| `backend/app/services/prediction/` | 禁止 | 禁止 | **書込** | 禁止 |
| `backend/app/api/endpoints/rankings.py` | 禁止 | 禁止 | **書込** | 禁止 |
| `frontend/` 全般 | 禁止 | **書込** | 禁止 | 禁止 |
| `backend/app/models/ad.py` | 追加のみ | 禁止 | 読取のみ | 読取のみ |
| `backend/app/models/ad_metrics.py` | 追加のみ | 禁止 | 追加のみ | 禁止 |
| `backend/app/schemas/ad.py` | 追加のみ | 禁止 | 追加のみ | 禁止 |

## ad_metadata キーの所有権

| キー | 書込担当 | 他は読取のみ |
|------|---------|------------|
| `estimated_audience_min/max` | Agent A | C が読む |
| `publisher_platforms` | Agent A | C が読む |
| `delivery_start_time/stop_time` | Agent A | C が読む |
| `is_still_running` | Agent A | C が読む |
| `estimation_method` | Agent A | C が読む |
| `impressions_from_audience` | Agent A | C が読む |
| `creative_quality` | Agent D | C が読む |
| `thumbnail_fixed` | Agent D | — |
| `media_urls_backfilled` | Agent D | — |
| `extraction_method` | Agent D | — |
| `media_extraction_status` | Agent D | — |
| `media_completeness_score` | Agent D | — |
| `media_quality_issues` | Agent D | — |
| `latest_hit_score` | Agent C | B がAPI経由で読む |
| `latest_score_breakdown` | Agent C | B がAPI経由で読む |
| `hit_level` | Agent C | B がAPI経由で読む |
| `is_hit` | Agent C | B がAPI経由で読む |
| `lp_status` | Agent C | B がAPI経由で読む |
| `lp_checked_at` | Agent C | — |
| `data_completeness` | Agent C | — |
| `last_checked_at` | Agent A | C が読む |
| `snapshot_check` | Agent A | — |
| `longevity_class` | Agent A | C が読む |
| `survival_checked_at` | Agent A | — |
| `score_updated_at` | Agent C | — |
| `freshness_score` | Agent A | C が読む |
| `freshness_computed_at` | Agent A | — |
| `auto_recrawl_scheduled` | Agent A | D が読む |
| `data_quality_issues` | Agent A | — |
| `video_analyzed` | Agent D | C が読む |
| `video_analyzed_at` | Agent D | — |
| `frame_count` | Agent D | — |
| `scene_count` | Agent D | — |
| `best_thumbnail_frame` | Agent D | — |
| `video_quality` | Agent D | C が読む |

## Phase 2 ファイル専有マップ（追加分）

| 領域 | Agent |
|------|-------|
| `backend/app/models/alert_rule.py` | Agent A |
| `backend/app/models/alert_history.py` | Agent A |
| `backend/app/services/alert_engine.py` | Agent A |
| `backend/app/services/data_freshness.py` | Agent A |
| `backend/app/services/data_quality_report.py` | Agent A |
| `backend/app/api/endpoints/ai_chat.py` | Agent C |
| `backend/app/services/ai/` | Agent C |
| `backend/app/models/conversation.py` | Agent C |
| `backend/app/api/endpoints/integrations.py` | Agent C |
| `backend/app/services/integrations/` | Agent C |
| `backend/app/services/notification_service.py` | Agent C |
| `backend/app/services/crawling/crawl_orchestrator.py` | Agent D |
| `backend/app/services/crawling/rate_limiter.py` | Agent D |
| `backend/app/services/crawling/crawl_stats.py` | Agent D |
| `backend/app/services/crawling/normalizer.py` | Agent D |
| `backend/app/services/crawling/platform_health.py` | Agent D |
| `backend/app/services/video_pipeline.py` | Agent D |
| `backend/app/services/thumbnail_selector.py` | Agent D |
| `backend/app/tasks/video_tasks.py` | Agent D |

## 実行優先度（3 Planner 体制）

詳細は各PLANNERファイルを参照:
- `PLANNER1_DATA_FOUNDATION.md` — Agent A + D の優先タスク
- `PLANNER2_API_VERIFICATION.md` — Agent C の優先タスク
- `PLANNER3_FRONTEND_E2E.md` — Agent B の優先タスク

```
データフロー:
Planner 1 (A+D: データ収集・品質) → Planner 2 (C: API検証) → Planner 3 (B: UI表示確認)

Planner 1 がデータを埋める
  → Planner 2 がスコア再計算 + API検証
    → Planner 3 がUI表示確認

並行可能: Planner 3 は独立してフロントE2E検証を進められる
```

## 継続改善タスク（運用ルール）
- `CONTINUOUS_IMPROVEMENT_BACKLOG.md` を改善タスクの単一ソースとする
- 追加形式: `CI-XXX | 優先度 | 担当 | タスク | 完了条件`
- 各サイクルで `P0` 最低1件 + `P1` 最低2件を実行する
- 完了時は行末に ` [DONE: YYYY-MM-DD]` を付与する

### コード品質改修（全Planner共通・並行実行可能）
各エージェントのINSTRUCTIONS.mdに「コード品質改修」セクションを追記済み。
既存コードのバグ修正・改善であり、新機能ではない。
各ファイルは専有領域なのでコンフリクトなし。

## ★ Round 2 指示書 (2026-03-01 発行) ★

`ROUND2_INSTRUCTIONS.md` を参照。Phase 1 残タスク消化 + Phase 2 着手開始。

## ★ DPro差分埋め設計書 (2026-03-02 追加) ★

`DPRO_PARITY_IMPLEMENTATION_SPEC.md` を参照。  
動画広告分析Proとの差分を埋めるための指標定義・API/UI仕様・実装順・受け入れ基準を記載。

各エージェントの次タスク:
- **A**: A-R2-1〜A-R2-6 (データ品質 → アラートエンジン)
- **B**: B-R2-1〜B-R2-6 (ダークモード → 通知センター)
- **C**: C-R2-1〜C-R2-5 (AIチャット → N+1解消)
- **D**: D-R2-1〜D-R2-6 (スケジュールクロール → 動画解析)

### Round 2 関連ドキュメント
```
ROUND2_INSTRUCTIONS.md          ← 全体戦略
ROUND2_PROGRESS_TRACKER.md      ← 23タスクの進捗管理
PLANNER1_DATA_FOUNDATION_R2.md  ← Planner 1 更新
PLANNER2_API_VERIFICATION_R2.md ← Planner 2 更新
PLANNER3_FRONTEND_E2E_R2.md     ← Planner 3 更新
VIEW_DEPENDENCY_MAP_R2.md       ← 依存関係マップ
VIEW_TEST_PLAN_R2.md            ← テスト計画
```

### 横断ドキュメント (Round 2 追加)
```
INTEGRATION_TEST_SCENARIOS.md   ← 10件の統合テストシナリオ
PERFORMANCE_BUDGET.md           ← パフォーマンス目標値
API_CONTRACT_REGISTRY.md        ← B↔C の API 契約書
INCIDENT_RUNBOOK.md             ← 障害対応手順書
QUALITY_GATE_CHECKLIST.md       ← 品質ゲート (全エージェント共通)
SECURITY_AUDIT_CHECKLIST.md     ← セキュリティ監査チェックリスト
DATA_FLOW_DIAGRAM.md            ← データフロー図
KPI_DEFINITIONS.md              ← KPI 定義・計測方法
PHASE2_DESIGN_SPEC.md           ← Phase 2 詳細設計
ROUND3_PREVIEW.md               ← Phase 3 準備
progress_report.sh              ← 進捗レポート自動生成
IMPLEMENTATION_PLAN_2026-03-03_CREATIVE_LIBRARY.md ← 2026-03-03 クリエイティブ取得強化の実装計画
```

### CI バックログ状況
```
Batch 1-5: CI-001〜CI-127 (127件)
Batch 6:   CI-128〜CI-141 (14件)
合計:      141件 (Agent A: 20件完了)
```

---

## 注意: C6 ファイル所有権の例外
C6タスクで `backend/scripts/check_lp_health.py` を Agent C が新規作成する。
これは `backend/scripts/` 内だが、LP検証はスコアリングパイプラインの一部であり、
結果を `ad_metadata.lp_status` に書き込み `rankings.py` のAPIで返すため Agent C が担当する。
Agent A は `check_lp_health.py` を触らないこと。
