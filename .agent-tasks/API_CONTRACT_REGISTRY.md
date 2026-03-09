# API Contract Registry

最終更新: 2026-03-01

## 目的
フロントエンド (Agent B) とバックエンド (Agent C) 間のAPI契約を明文化し、
破壊的変更を防止する。

---

## 命名規則

- バックエンド: `snake_case` (Python/PostgreSQL)
- フロントエンド: `camelCase` (TypeScript)
- 両方を `||` で受ける: `imageUrl={data.image_url || data.imageUrl}`

---

## Critical APIs (破壊禁止)

### 1. GET /api/v1/rankings/hit-ads

**用途**: HitAdAnalysisView のメインデータソース

```typescript
// Request
GET /api/v1/rankings/hit-ads?genre={genre}&limit={limit}&offset={offset}

// Response
{
  "ads": [
    {
      "id": number,
      "ad_id": string,
      "title": string,
      "advertiser_name": string,
      "genre": string,
      "platform": string,
      "creative_type": "video" | "image",
      "hit_score": number,          // 0-100
      "hit_level": "mega_hit" | "hit" | "rising" | "none",
      "is_hit": boolean,
      "trend_score": number,
      "estimated_spend": number,
      "estimated_views": number,
      "view_count": number,
      "like_count": number,
      "days_running": number,
      "is_still_running": boolean,
      "destination_url": string | null,
      "image_url": string | null,
      "video_url": string | null,
      "thumbnail_url": string | null,
      "snapshot_url": string | null,
      "duration_seconds": number | null,
      "delivery_start_time": string | null,
      "score_breakdown": object | null,
      "ad_metadata": object | null
    }
  ],
  "total": number,
  "limit": number,
  "offset": number
}
```

**フロントエンドの依存箇所**:
- `HitAdAnalysisView.tsx` — fetchData()
- `AdDetailModal.tsx` — 広告データ表示
- `ProRankingTable.tsx` — フォールバック

---

### 2. GET /api/v1/rankings/pro-ranking

**用途**: ProRankingTable のメインデータソース

```typescript
// Request
GET /api/v1/rankings/pro-ranking?limit={limit}&offset={offset}&genre={genre}&period={period}&sort_by={sort}&search={text}

// Response
{
  "ads": [
    {
      "rank": number,
      "id": number,
      "ad_id": string,
      "title": string,
      "advertiser_name": string,
      "genre": string,
      "platform": string,
      "creative_type": string,
      "duration_seconds": number | null,
      "hit_score": number,
      "hit_level": string,
      "view_count": number,
      "view_count_increase": number,     // ★ A-R2-2 で追加予定
      "estimated_spend": number,
      "spend_increase": number,          // ★ A-R2-2 で追加予定
      "like_count": number,
      "like_increase": number,           // ★ A-R2-2 で追加予定
      "trend_score": number,
      "is_still_running": boolean,
      "image_url": string | null,
      "thumbnail_url": string | null
    }
  ],
  "total": number,
  "hit_line_score": number,
  "period": string,
  "has_more": boolean
}
```

**フロントエンドの依存箇所**:
- `ProRankingTable.tsx` — テーブル表示
- `ProRankingView.tsx` — コンテナ

---

### 3. GET /api/v1/rankings/dashboard-summary

**用途**: サマリーカードのデータソース

```typescript
// Response
{
  "total_ads": number,
  "active_ads": number,
  "mega_hit_count": number,
  "hit_count": number,
  "avg_score": number,
  "top_genre": string,
  "top_creative_type": string,
  "data_freshness": string        // "fresh" | "stale" | "unknown"
}
```

**フロントエンドの依存箇所**:
- `HitAdAnalysisView.tsx` — サマリーカード6枚

---

### 4. GET /api/v1/rankings/score-breakdown/{ad_id}

**用途**: スコア内訳ポップオーバー / AdDetailModal

```typescript
// Response
{
  "ad_id": string,
  "total_score": number,
  "signals": [
    {
      "name": string,           // "longevity" | "spend" | "active_bonus" | "creative" | "trend"
      "label": string,
      "value": number,
      "max_value": number,
      "detail": string
    }
  ]
}
```

**フロントエンドの依存箇所**:
- `HitAdAnalysisView.tsx` — スコアポップオーバー
- `AdDetailModal.tsx` — スコア内訳表示

---

### 5. GET /api/v1/rankings/genre-comparison

**用途**: ジャンル比較チャート

```typescript
// Response
{
  "genres": [
    {
      "genre": string,
      "ad_count": number,       // or "total_ads"
      "avg_score": number,      // or "avg_hit_score"
      "hit_rate": number,       // 0.0-1.0
      "avg_spend": number
    }
  ]
}
```

**フロントエンドの依存箇所**:
- `HitAdAnalysisView.tsx` — ジャンル比較横棒グラフ

---

### 6. GET /api/v1/rankings/score-distribution

**用途**: スコア分布チャート

```typescript
// Response
{
  "distribution": [
    { "range": string, "count": number }     // "0-10", "10-20", ...
  ],
  "mean": number,
  "median": number,
  "hit_count": number,
  "mega_hit_count": number,
  "total": number
}
```

---

### 7. GET /api/v1/media/thumbnail/{ad_id}

**用途**: 全コンポーネントのサムネイル表示

```typescript
// Response: 302 redirect to S3 URL, or 200 with image binary
// Content-Type: image/jpeg | image/png | image/webp

// Error: 404 { "detail": "Thumbnail not found" }
```

**フロントエンドのフォールバックチェーン**:
1. `/api/v1/media/thumbnail/{ad_id}` (proxy)
2. `thumbnail_url` (direct)
3. `image_url` (direct)
4. `snapshot_url` (direct)
5. プレースホルダー SVG

---

### 7a. Creative Library `media_status` Contract

**用途**: Creative Library / Ad detail / Rankings 一覧で「見れる / DLできる / LP有無」を追加 API 推測なしで描画する

```typescript
{
  "media_status": {
    "viewable": boolean,
    "downloadable": boolean,
    "has_lp": boolean,
    "primary_type": "video" | "image" | "thumbnail" | "unknown",
    "missing_reasons": Array<
      "missing_creative" |
      "download_unavailable" |
      "snapshot_only" |
      "lp_missing" |
      "lp_unresolved"
    >
  },
  "media_cache_status": "cached" | "partial" | "uncached" | "full" | "none"
}
```

```json
{
  "media_status": {
    "viewable": true,
    "downloadable": false,
    "has_lp": true,
    "primary_type": "unknown",
    "missing_reasons": ["snapshot_only", "download_unavailable"]
  },
  "media_cache_status": "none"
}
```

**同梱先**:
- `GET /api/v1/rankings/*` の広告一覧・詳細系レスポンス
- `GET /api/v1/media/status/{ad_id}`
- `GET /api/v1/ads/{ad_id}/media`

**備考**:
- `media_status` が正契約
- `media_cache_status` は後方互換の補助情報

---

### 7b. POST /api/v1/media/bulk-download

**用途**: Creative Library の一括DL

```typescript
// Success
{
  "download_url": string,
  "requested_count": number,
  "downloaded_count": number,
  "file_count": number,
  "total_size_bytes": number,
  "zip_filename": string,
  "skipped_ids": number[],
  "skipped_reasons": Record<string,
    "missing_creative" |
    "download_unavailable" |
    "snapshot_only" |
    "lp_missing" |
    "lp_unresolved"
  >,
  "skipped_reason_code": "no_cached_media" | null
}

// Error detail
{
  "detail": {
    "failure_reason_code":
      "no_cached_media" |
      "zip_creation_failed" |
      "invalid_ad_ids" |
      "download_file_missing",
    "message": string
  }
}
```

```json
{
  "download_url": "/api/v1/media/bulk-download-file/ads_media_20260308_120000_abcd1234.zip",
  "requested_count": 2,
  "downloaded_count": 1,
  "file_count": 1,
  "total_size_bytes": 84231,
  "zip_filename": "ads_media_20260308_120000_abcd1234.zip",
  "skipped_ids": [102],
  "skipped_reasons": {
    "102": "snapshot_only"
  },
  "skipped_reason_code": "no_cached_media"
}
```

**B が参照すべき必須フィールド**:
- success: `download_url`, `requested_count`, `downloaded_count`, `skipped_ids`, `skipped_reasons`, `skipped_reason_code`
- error: `detail.failure_reason_code`, `detail.message`

---

### 7c. Creative Library `lp_info` Contract

**用途**: LP 遷移先の解決結果を Creative Library / 詳細画面 / 監査で共通利用する

```typescript
{
  "lp_info": {
    "destination_url": string | null,
    "domain": string,
    "destination_type": string,
    "lp_status": "alive" | "redirect" | "dead" | "unreachable" | "unresolved",
    "lp_score": number | null,
    "has_lp": boolean,
    "resolved_url": string | null,
    "redirect_chain": string[],
    "final_domain": string,
    "http_status": number | null
  }
}
```

```json
{
  "lp_info": {
    "destination_url": "https://example.com/lp",
    "domain": "example.com",
    "destination_type": "lp",
    "lp_status": "redirect",
    "lp_score": null,
    "has_lp": true,
    "resolved_url": "https://lp.example-cdn.com/final",
    "redirect_chain": [
      "https://example.com/lp",
      "https://lp.example-cdn.com/final"
    ],
    "final_domain": "lp.example-cdn.com",
    "http_status": 302
  }
}
```

**同梱先**:
- `GET /api/v1/ads/{ad_id}/media`
- `GET /api/v1/media/status/{ad_id}`

---

### 8. GET /api/v1/rankings/smart-autocomplete

**用途**: SmartSearchBar のオートコンプリート

```typescript
// Request
GET /api/v1/rankings/smart-autocomplete?q={query}&limit={limit}

// Response
{
  "suggestions": [
    {
      "type": "all" | "genre" | "advertiser" | "product",
      "value": string,
      "label": string,
      "count": number | null
    }
  ]
}
```

---

### 9. GET /api/v1/rankings/genre-master

**用途**: ProRankingView のジャンルサイドバー

```typescript
// Response
{
  "genres": [
    {
      "id": string,
      "name": string,
      "parent": string | null,
      "count": number,
      "children": [
        { "id": string, "name": string, "count": number }
      ]
    }
  ]
}
```

---

### 10. GET /api/v1/rankings/hit-factors

**用途**: HitPatternPanel, WinningFormulas

```typescript
// Request
GET /api/v1/rankings/hit-factors?genre={genre}

// Response
{
  "hook_types": [
    { "type": string, "hit_rate": number, "count": number }
  ],
  "cta_types": [
    { "type": string, "hit_rate": number, "count": number }
  ],
  "offer_types": [
    { "type": string, "hit_rate": number, "count": number }
  ],
  "emotions": [
    { "type": string, "hit_rate": number, "count": number }
  ],
  "winning_patterns": [
    {
      "hook": string, "cta": string, "offer": string, "emotion": string,
      "hit_rate": number, "count": number,
      "example_ads": [ { "ad_id": string, "title": string } ]
    }
  ]
}
```

---

### 11. POST /api/v1/rankings/quick-crawl

**用途**: 検索UIからの即時クロール実行（Meta 2面をデフォルト対象）

```typescript
// Request
{
  "query": string,                   // 必須（全角スペースは正規化）
  "limit"?: number,                  // default: 20
  "platforms"?: string[] | null,     // 未指定時: ["facebook","instagram"]
  "country"?: string                 // default: "JP"
}

// Success Response (200)
{
  "status": "completed",
  "job_id": string,
  "platforms": string[],
  "country": string,
  "fetched_ads_count": number,       // 取得件数
  "new_ads_count": number,
  "inserted_count": number,
  "updated_count": number,
  "saved_ads_count": number,         // 保存件数
  "searchable_ads_count": number,    // 検索可視件数
  "dropped_after_filter_count": number,
  "visible_gap_count": number,
  "total_ads_found": number,
  "ads_found": number,
  "error_code": null,
  "failure_reason": null
}

// Failure Response (500)
{
  "status": "failed",
  "job_id": string,
  "error": string,
  "detail": string,
  "error_code": string,              // timeout/rate_limit/auth_expired/...
  "failure_reason": string,
  "platforms": string[],
  "country": string
}
```

---

### 12. POST /api/v1/rankings/classify-topic

**用途**: 広告文/説明文/LP文面（または `ad_id`）からトピック分類を返却し、根拠を可視化

```typescript
// Request
{
  "ad_id"?: number,              // ad_id 指定時はDB広告を分類
  "text"?: string,               // 生テキスト分類
  "description"?: string,
  "advertiser_name"?: string,
  "lp_text"?: string
}

// Response
{
  "ad_id": number | null,
  "topic_tags": string[],        // 上位トピックラベル
  "confidence": number,          // primary confidence (0-1)
  "evidence_terms": string[],    // 根拠語
  "hit_drivers": string[],       // HIT寄与要素
  "model_version": string,       // "topic-heuristic-v1.0.0"
  "scores": { [topic: string]: number }
}
```

---

### 13. GET /api/v1/rankings/topic-gap-report

**用途**: 期待分類量と保存済み分類量の乖離をカテゴリ横断で監査

```typescript
// Request
GET /api/v1/rankings/topic-gap-report?false_negative_limit=20

// Response
{
  "generated_at": string,
  "summary": {
    "expected_volume": number,
    "classified_volume": number,
    "gap": number
  },
  "categories": [
    {
      "topic_label": string,
      "expected_volume": number,
      "classified_volume": number,
      "gap": number,
      "false_negative_candidates": [
        {
          "ad_id": number,
          "title": string,
          "expected_topic": string,
          "classified_topic": string,
          "confidence": number,
          "evidence_terms": string[]
        }
      ]
    }
  ]
}
```

---

### 14. POST /api/v1/rankings/quality-gate/evaluate

**用途**: クロール/分類結果の品質ゲート判定（最低件数・充足率・画像品質・分類信頼度）

```typescript
// Request
{
  "ad_ids"?: number[],
  "min_count"?: number,                 // default: 10
  "min_required_fill_rate"?: number,    // 0-1, default: 0.8
  "min_image_quality_score"?: number,   // 0-100, default: 40
  "min_topic_confidence"?: number       // 0-1, default: 0.6
}

// Response
{
  "passed": boolean,
  "evaluated_at": string,
  "sample_count": number,
  "metrics": {
    "required_fill_rate": number,
    "avg_image_quality_score": number,
    "avg_topic_confidence": number
  },
  "thresholds": {
    "min_count": number,
    "min_required_fill_rate": number,
    "min_image_quality_score": number,
    "min_topic_confidence": number
  },
  "reasons": [
    {
      "code": string,       // minimum_count_not_met, required_fields_fill_rate_low, ...
      "metric": string,
      "actual": number,
      "threshold": number,
      "message": string,
      "suggestion": string
    }
  ],
  "suggestions": string[]
}
```

---

## Phase 2 APIs (新規予定)

### POST /api/v1/ai-chat/message (C-R2-1)

```typescript
// Request
{
  "message": string,
  "conversation_id": string | null
}

// Response
{
  "response": string,
  "intent": string,
  "conversation_id": string,
  "structured_data": object | null
}
```

### GET /api/v1/notifications (C-R2-2)

```typescript
// Response
{
  "notifications": [
    {
      "id": number,
      "type": string,
      "title": string,
      "message": string,
      "is_read": boolean,
      "created_at": string,
      "metadata": object | null
    }
  ],
  "unread_count": number
}
```

---

## 変更管理ルール

1. **既存フィールドの削除・型変更は禁止**（破壊的変更）
2. **フィールド追加は OK**（フロントエンドは未知フィールドを無視する）
3. **フィールド名変更時は旧名を 2 スプリント併存**
4. **エラーレスポンスは統一形式** `{ "detail": string, "code": string }`
5. **ページネーションは統一** `{ "total": number, "limit": number, "offset": number }`
6. **日付は ISO 8601** `"2026-03-01T12:00:00Z"`
7. **変更時は COORDINATION_LOG.md に記録**

### 15. POST /api/v1/rankings/dictionary/suggest

**用途**: 広告メタデータの根拠語からトピック辞書の追加候補を提案

```typescript
// Request
{
  "from_date"?: string,            // YYYY-MM-DD
  "to_date"?: string,              // YYYY-MM-DD
  "topic_labels"?: string[],
  "ad_ids"?: number[],
  "limit"?: number                 // default: 20, max: 200
}

// Response
{
  "generated_at": string,
  "candidate_terms": [
    {
      "topic_label": string,
      "term": string,
      "count": number,
      "reason": string,
      "confidence": number,
      "sample_ad_ids": number[]
    }
  ],
  "meta": {
    "scanned_ads": number,
    "topics": string[],
    "limit": number
  }
}
```

---

### 16. POST /api/v1/rankings/dictionary/review

**用途**: 辞書候補のレビュー結果（adopt/hold/reject）を永続化し、adoptは分類器辞書へ反映

```typescript
// Request
{
  "reviewer"?: string,
  "items": [
    {
      "topic_label": string,
      "term": string,
      "decision": "adopt" | "hold" | "reject",
      "note"?: string,
      "confidence"?: number,
      "reason"?: string
    }
  ]
}

// Response
{
  "saved": number,
  "reviewed_at": string,
  "summary": {
    "adopt": number,
    "hold": number,
    "reject": number,
    "applied_terms": number
  },
  "dictionary_sizes": {
    [topic: string]: number
  }
}
```

---

### 17. POST /api/v1/rankings/knowledge/rebuild

**用途**: 定期/手動クロール後の知識再構築とスナップショット版管理

```typescript
// Request
{
  "source"?: "manual" | "scheduled" | "post_crawl",
  "trigger_job_id"?: string,
  "include_recent_days"?: number,
  "max_ads"?: number
}

// Response
{
  "ok": boolean,
  "snapshot": {
    "version": string,
    "created_at": string,
    "source": string,
    "trigger_job_id": string | null,
    "window_days": number,
    "scanned_ads": number,
    "dictionary": {
      "topic_count": number,
      "total_terms": number,
      "terms_per_topic": { [topic: string]: number },
      "applied_terms_from_reviews": number
    },
    "classification": {
      "topic_counts": { [topic: string]: number },
      "unknown_count": number,
      "avg_confidence": number
    }
  },
  "total_snapshots": number
}
```

### 18. GET /api/v1/rankings/ad360/{ad_id}

**用途**: 1広告の描画に必要な情報を単一契約で返却（構造固定）

```typescript
// Response
{
  "ad_id": number,
  "sections": {
    "core": {
      "data": {
        "ad_id": number,
        "external_id": string,
        "title": string,
        "advertiser_name": string,
        "platform": string,
        "genre": string,
        "created_at": string | null,
        "first_seen_at": string | null,
        "last_seen_at": string | null,
        "destination_url": string
      },
      "missing_fields": string[]
    },
    "creative": {
      "data": {
        "creative_type": string,
        "thumbnail_url": string,
        "image_url": string,
        "video_url": string,
        "snapshot_url": string,
        "duration_seconds": number,
        "media_status": string,
        "extract_source": string
      },
      "missing_fields": string[]
    },
    "text": {
      "data": {
        "title": string,
        "description": string,
        "ocr_texts": string[],
        "transcript": string,
        "hook_text": string,
        "cta_text": string
      },
      "missing_fields": string[]
    },
    "analysis": {
      "data": {
        "hit_score": number,
        "hit_level": string,
        "is_hit": boolean,
        "days_running": number,
        "topic_label": string,
        "topic_confidence": number,
        "topic_tags": string[],
        "matched_terms": string[],
        "needs_topic_review": boolean,
        "creative_analysis": object,
        "ad_analysis": object
      },
      "missing_fields": string[]
    },
    "lp": {
      "data": {
        "has_lp": boolean,
        "lp_id": number | null,
        "url": string,
        "final_url": string,
        "domain": string,
        "title": string,
        "lp_type": string,
        "status": string,
        "lp_score": number | null,
        "conversion_potential_score": number | null,
        "trust_score": number | null,
        "urgency_score": number | null
      },
      "missing_fields": string[]
    },
    "quality": {
      "data": {
        "needs_media_retry": boolean,
        "extract_quality_score": number,
        "media_status": string,
        "topic_confidence": number,
        "quality_flags": object
      },
      "missing_fields": string[]
    }
  }
}
```

### 19. GET /api/v1/rankings/meta-extraction/{ad_id}

**用途**: Meta広告粒度（ad_id）で抽出状態を固定構造で取得

```typescript
// Response
{
  "ad_id": number,
  "creative_urls": {
    "image": string,
    "video": string,
    "thumbnail": string,
    "snapshot": string
  },
  "text_fields": {
    "title": string,
    "description": string,
    "ocr": string[],
    "transcript": string
  },
  "extract_source": string,
  "quality_score": number,
  "missing_fields": string[]
}
```

---

### 20. POST /api/v1/rankings/meta-extraction/{ad_id}/retry

**用途**: 再抽出を段階実行（API→Browser→Fallback）し、結果と失敗理由コードを返却

```typescript
// Response (success)
{
  "ad_id": number,
  "dispatched": true,
  "message_id": string | null,
  "strategy": [
    {
      "stage": "api" | "browser" | "fallback",
      "status": "dispatched" | "failed" | "skipped",
      "message_id"?: string,
      "error_code"?: string,
      "detail"?: string
    }
  ],
  "failure_reason_code": null
}

// Response (failed)
{
  "ad_id": number,
  "dispatched": false,
  "strategy": [...],
  "failure_reason_code": string,
  "detail": string
}
```

### 21. GET /api/v1/rankings/quick-crawl/{job_id}/consistency

**用途**: crawl→search反映整合を job_id 単位で判定

```typescript
// Response
{
  "job_id": string,
  "status": string,
  "db_inserted_count": number,
  "search_visible_count": number,
  "delta": number,
  "is_consistent": boolean,
  "checked_at": string
}
```

---

### 22. GET /api/v1/rankings/lp-info/{ad_id}

**用途**: LP取得結果の観測API（取得成功/失敗を同一構造で返却）

```typescript
// Response
{
  "ad_id": number,
  "fetch_status": string,
  "error_code": string | null,
  "title": string,
  "description": string,
  "canonical": string,
  "og_image": string,
  "final_url": string,
  "http_status": number,
  "fetched_at": string | null
}
```

---

### 23. POST /api/v1/rankings/lp-info/refresh

**用途**: 指定広告のLP再取得タスクを一括ディスパッチ

```typescript
// Request
{
  "ad_ids": number[],
  "force"?: boolean
}

// Response
{
  "requested": number,
  "dispatched": number,
  "errors": number,
  "missing_ad_ids": number[],
  "details": [{ "ad_id": number, "message_id": string }]
}
```

---

### 24. Real Metrics Provenance Contract

**用途**: `ads` と `rankings` の数値系 UI を同じ shape で描画し、実測/推定/欠損/古さを安全に表示する

```typescript
type MetricProvenance = {
  metric_source: string
  metric_status: "real" | "estimated" | "missing"
  freshness_status: "fresh" | "stale" | "unknown"
  measured_at: string | null
  confidence_label: "high" | "medium" | "low" | "none"
}

type RealMetricsFields = {
  spend: number | null
  spend_provenance: MetricProvenance
  impressions: number | null
  impressions_provenance: MetricProvenance
  reach: number | null
  reach_provenance: MetricProvenance
  lp_score: number | null
  lp_score_provenance: MetricProvenance
  extract_quality_score: number | null
  extract_quality_score_provenance: MetricProvenance
}
```

---

### 25. Language & Product Taxonomy Contract

**用途**: `ads` と `rankings/search` 系で言語判定と商材分類を同じ field 名で安全に扱う

```typescript
{
  "language": string,                 // "ja" | BCP47-like raw tag | "unknown"
  "language_status": "ja" | "non-ja" | "unknown",
  "language_confidence": number,      // 0.0 - 1.0
  "language_source": string,          // "bedrock" | "rule" | "rule_text" | "missing" ...
  "product_category": string,
  "product_subcategory": string,
  "exclude_from_analysis": boolean,
  "exclude_reason": string | null
}
```

---

### 26. Bedrock Classification Gateway Contract

**用途**: Bedrock 分類結果を backend 内で同一 shape に正規化し、partial / timeout / fallback を安定語彙で扱う

```typescript
{
  "ad_id": number | null,
  "language": string,
  "product_category": string,
  "topic_label": string,
  "confidence": number,
  "reasons": string[],
  "model_name": string,
  "classified_at": string | null,
  "status": "success" | "partial" | "fallback" | "timeout" | "missing",
  "fallback_applied": boolean,
  "partial_fields": string[],
  "error_code": string | null,
  "source_priority": ["bedrock_result", "rule_fallback"]
}
```

```json
{
  "ad_id": 123,
  "language": "ja",
  "product_category": "beauty",
  "topic_label": "medical_diet",
  "confidence": 0.95,
  "reasons": ["bedrock_result_used"],
  "model_name": "anthropic.claude-3-5-sonnet",
  "classified_at": "2026-03-08T09:00:00+00:00",
  "status": "success",
  "fallback_applied": false,
  "partial_fields": [],
  "error_code": null,
  "source_priority": ["bedrock_result", "rule_fallback"]
}
```

**Semantics**
- `language_status = "ja"`: Japanese content and JP-only analysis対象
- `language_status = "non-ja"`: Japanese targeting外として除外対象
- `language_status = "unknown"`: 判定材料が足りず、除外理由を確定できない

```json
{
  "language": "ja",
  "language_status": "ja",
  "language_confidence": 0.95,
  "language_source": "bedrock",
  "product_category": "beauty",
  "product_subcategory": "medical_weight_loss",
  "exclude_from_analysis": false,
  "exclude_reason": null
}
```

**Reason code / enum**
- `real`
- `estimated`
- `missing`
- `stale`

```json
{
  "spend": 5400,
  "spend_provenance": {
    "metric_source": "observed_spend",
    "metric_status": "real",
    "freshness_status": "fresh",
    "measured_at": "2026-03-08T09:00:00+00:00",
    "confidence_label": "high"
  },
  "impressions": 2400,
  "impressions_provenance": {
    "metric_source": "observed_impressions",
    "metric_status": "real",
    "freshness_status": "fresh",
    "measured_at": "2026-03-08T09:00:00+00:00",
    "confidence_label": "high"
  },
  "reach": null,
  "reach_provenance": {
    "metric_source": "missing",
    "metric_status": "missing",
    "freshness_status": "unknown",
    "measured_at": null,
    "confidence_label": "none"
  },
  "lp_score": 72,
  "lp_score_provenance": {
    "metric_source": "lp_analysis",
    "metric_status": "real",
    "freshness_status": "fresh",
    "measured_at": "2026-03-08T09:00:00+00:00",
    "confidence_label": "high"
  },
  "extract_quality_score": 81,
  "extract_quality_score_provenance": {
    "metric_source": "creative_extraction",
    "metric_status": "real",
    "freshness_status": "fresh",
    "measured_at": "2026-03-08T09:00:00+00:00",
    "confidence_label": "high"
  }
}
```

---

### 27. Bedrock Decision Contract and Prompt Registry

**用途**: Bedrock 分類結果を意思決定 payload に正規化し、prompt/version/model の provenance と fallback 振る舞いを固定する

```typescript
{
  "ad_id": number | null,
  "language": string,
  "product_category": string,
  "product_subcategory": string,
  "topic_label": string,
  "offer_type": string,
  "funnel_type": string,
  "priority_score": number,
  "priority_reason": "rule_override" | "bedrock_priority_score" | "rule_priority_score",
  "review_required": boolean,
  "review_reason": string | null,
  "confidence_band": "high" | "medium" | "low",
  "model_name": string,
  "prompt_version": string,
  "classified_at": string | null,
  "status": "success" | "partial" | "fallback" | "timeout" | "missing",
  "fallback_applied": boolean,
  "error_code": string | null,
  "source_priority": ["rule_override", "bedrock_result", "rule_fallback"]
}
```

```json
{
  "ad_id": 123,
  "language": "ja",
  "product_category": "beauty",
  "product_subcategory": "medical_weight_loss",
  "topic_label": "medical_diet",
  "offer_type": "discount",
  "funnel_type": "single_lp",
  "priority_score": 88.0,
  "priority_reason": "bedrock_priority_score",
  "review_required": false,
  "review_reason": null,
  "confidence_band": "high",
  "model_name": "anthropic.claude-3-5-sonnet",
  "prompt_version": "classification-v1",
  "classified_at": "2026-03-08T09:00:00+00:00",
  "status": "success",
  "fallback_applied": false,
  "error_code": null,
  "source_priority": ["rule_override", "bedrock_result", "rule_fallback"]
}
```

**Fallback contract**
- `timeout`: `status = "timeout"`, `fallback_applied = true`, `review_required = true`, `review_reason = "bedrock_timeout"`
- `partial`: `status = "partial"`, `fallback_applied = true`, `review_required = true`, `review_reason = "partial_bedrock_result"`
- `invalid_json`: `status = "fallback"`, `fallback_applied = true`, `review_required = true`, `review_reason = "invalid_json"`

**Prompt registry**

```json
{
  "default_prompt_version": "classification-v1",
  "items": [
    {
      "prompt_version": "classification-v1",
      "model_name": "anthropic.claude-3-5-sonnet",
      "task": "language_product_topic_classification",
      "required_output_fields": [
        "language",
        "product_category",
        "product_subcategory",
        "topic_label",
        "offer_type",
        "funnel_type",
        "priority_score",
        "review_required"
      ]
    }
  ]
}
```

---

### 28. Bedrock Review Queue and Priority API

**用途**: priority / review_required / provenance を一覧系 API で安定提供し、actual metrics 取得優先対象と review queue を同じ語彙で扱う

```typescript
{
  "ad_id": number,
  "title": string,
  "advertiser_name": string,
  "platform": string,
  "product_name": string,
  "priority_score": number,
  "priority_bucket": "high" | "medium" | "low",
  "priority_reason": "rule_override" | "bedrock_priority_score" | "rule_priority_score",
  "review_required": boolean,
  "review_reason": string | null,
  "confidence_band": "high" | "medium" | "low",
  "actual_metrics_present": boolean,
  "actual_metrics_focus": boolean,
  "provenance_summary": "rule" | "ai" | "manual",
  "provenance": {
    "language": "rule" | "ai" | "manual",
    "product_category": "rule" | "ai" | "manual",
    "topic_label": "rule" | "ai" | "manual",
    "priority": "rule" | "ai" | "manual",
    "review": "rule" | "ai" | "manual"
  }
}
```

```json
{
  "total": 2,
  "limit": 20,
  "filters": {
    "q": null,
    "only_high_priority": true,
    "only_review_required": false,
    "priority_min": 70.0
  },
  "items": [
    {
      "ad_id": 123,
      "title": "GLP-1 医療ダイエット",
      "advertiser_name": "Clinic A",
      "platform": "facebook",
      "product_name": "medical_diet",
      "priority_score": 86.0,
      "priority_bucket": "high",
      "priority_reason": "bedrock_priority_score",
      "review_required": true,
      "review_reason": "manual_review_required",
      "confidence_band": "low",
      "actual_metrics_present": false,
      "actual_metrics_focus": true,
      "provenance_summary": "ai",
      "provenance": {
        "language": "ai",
        "product_category": "ai",
        "topic_label": "ai",
        "priority": "ai",
        "review": "manual"
      }
    }
  ]
}
```

**Filter contract**
- `only_high_priority=true`: `priority_bucket == "high"` のみ返す
- `only_review_required=true`: `review_required == true` のみ返す
- `priority_min`: `priority_score >= priority_min` のみ返す
- `q`: `title / advertiser_name / product_name / product_category / topic_label / review_reason` に対する部分一致

---

### 29. Meta Data Contract and Freshness API

**用途**: Meta 広告由来の provenance / freshness / quality 状態を `ads` と `rankings` で同一 shape で返す

```typescript
{
  "metric_source": "api" | "estimated" | "missing" | "stale",
  "creative_source": "api" | "browser" | "playwright_render_ad" | "missing",
  "lp_source": "api" | "browser" | "httpx" | "missing",
  "metric_status": "real" | "estimated" | "missing" | "stale",
  "creative_status": "real" | "missing",
  "lp_status": "real" | "missing",
  "freshness_status": "fresh" | "stale" | "unknown",
  "last_meta_success_at": string | null,
  "meta_quality_state": "real" | "estimated" | "missing" | "stale",
  "meta_recovery_reason": string | null
}
```

```json
{
  "metric_source": "api",
  "creative_source": "playwright_render_ad",
  "lp_source": "httpx",
  "metric_status": "real",
  "creative_status": "real",
  "lp_status": "real",
  "freshness_status": "fresh",
  "last_meta_success_at": "2026-03-08T09:00:00+00:00",
  "meta_quality_state": "real",
  "meta_recovery_reason": "detail_enrich_failed"
}
```

**Semantics**
- `metric_source`: 数値メトリクスの由来
- `creative_source`: クリエイティブ参照の由来
- `lp_source`: LP 解決の由来
- `meta_quality_state`: API 契約上の総合品質状態。`partial` などの内部状態は `real / estimated / missing / stale` に正規化する
