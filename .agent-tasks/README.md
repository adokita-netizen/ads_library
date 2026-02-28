# Agent Tasks — タスク管理ディレクトリ

## 構成
```
.agent-tasks/
├── README.md              ← このファイル
├── A/                     ← Agent A: バックエンド・データ基盤
│   ├── INSTRUCTIONS.md
│   ├── A_サムネイル品質修復.md          [済]
│   ├── A2_リアルメトリクス収集パイプライン.md  [済]
│   ├── A3_データ品質パイプライン.md      [済]
│   ├── A4_データ鮮度とエクスポート.md    [済]
│   └── status.md
├── B/                     ← Agent B: フロントエンド
│   ├── INSTRUCTIONS.md
│   ├── B_〜B5                           [済]
│   ├── B6_LP表示とダッシュボード改善.md  [進行中]
│   ├── log.md / status.md
├── C/                     ← Agent C: バックエンド・スコアリング
│   ├── INSTRUCTIONS.md
│   ├── C_〜C5                           [済]
│   ├── C6_データ精度向上API.md          [次]
│   └── status.md
└── D/                     ← Agent D: メディア・クローリング
    ├── INSTRUCTIONS.md
    ├── D1_メディア品質パイプライン.md    [済]
    ├── D2_クローリング改善.md           [済]
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

## 実行順序
```
Agent A (データ収集)  →  Agent C (スコア計算)  →  Agent B (UI表示)
       ↓                      ↓                     ↓
  Meta API実データ        マルチシグナル          カード表示
  生存チェック            スコア計算             比較機能
  データ品質             API拡張               ダッシュボード
  エクスポート           LP検証                信頼度表示

Agent D (メディア・クローリング) — A/C と並行実行可能
       ↓
  動画URL抽出
  サムネイル修復
  メディアステータス管理
  クローラー改善
```
Agent B は A/C/D と並行実行可能（フロントは独立）。
ただし C のAPI拡張を反映するUI部分は C 完了後に最終調整。

## 注意: C6 ファイル所有権の例外
C6タスクで `backend/scripts/check_lp_health.py` を Agent C が新規作成する。
これは `backend/scripts/` 内だが、LP検証はスコアリングパイプラインの一部であり、
結果を `ad_metadata.lp_status` に書き込み `rankings.py` のAPIで返すため Agent C が担当する。
Agent A は `check_lp_health.py` を触らないこと。
