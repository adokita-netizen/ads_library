# VAAP Data Flow Diagram

最終更新: 2026-03-01

## 目的
データの流れを可視化し、各エージェントの責任範囲と結合点を明確にする。

---

## 1. 広告データの全体フロー

```
                            ┌─────────────────────┐
                            │   Meta Ad Library    │
                            │   (External API)     │
                            └──────────┬──────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌───────────┐    ┌───────────────┐    ┌───────────┐
            │ API Crawl  │    │ Browser Crawl │    │ Scheduled  │
            │ meta_crawler│    │ Playwright    │    │ EventBridge│
            │ [Agent D]  │    │ [Agent D]     │    │ [Agent D]  │
            └─────┬──────┘    └──────┬────────┘    └─────┬──────┘
                  │                  │                   │
                  └────────┬─────────┴───────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  crawl_tasks.py │
                  │  _merge_data() │
                  │  [Agent D]     │
                  └────────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
     ┌──────────────┐ ┌─────────┐ ┌──────────────┐
     │  ad (table)   │ │ ad_daily │ │ ad_metadata  │
     │  - title      │ │ _metrics │ │  (JSONB)     │
     │  - ad_id      │ │  [A]     │ │  [A+C+D]    │
     │  - genre      │ └────┬────┘ └──────────────┘
     │  - platform   │      │
     │  - urls       │      │
     └──────┬────────┘      │
            │               │
     ┌──────┴────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                     DATA PROCESSING                      │
├──────────────┬──────────────┬──────────────┬────────────┤
│ [Agent A]    │ [Agent D]    │ [Agent C]    │ [Agent A]  │
│ classify_ads │ extract_media│ recompute_   │ collect_   │
│ fix_titles   │ fix_thumbnails│ hit_scores  │ real_metrics│
│ fix_urls     │ backfill_urls│              │ check_     │
│ collect_dates│              │              │ survival   │
└──────┬───────┴──────┬───────┴──────┬───────┴─────┬──────┘
       │              │              │             │
       ▼              ▼              ▼             ▼
  ┌─────────┐   ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ ad_     │   │ S3 media │  │ product_ │  │ ad_daily │
  │ metadata│   │ bucket   │  │ ranking  │  │ _metrics │
  │ (genre, │   │ (images, │  │ (scores, │  │ (views,  │
  │  titles)│   │  videos) │  │  ranks)  │  │  spend)  │
  └────┬────┘   └────┬─────┘  └────┬─────┘  └────┬─────┘
       │             │             │              │
       └─────────────┴──────┬──────┴──────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │   API Layer    │
                   │  rankings.py   │
                   │  [Agent C]     │
                   └────────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │  /hit-ads    │ │ /pro-    │ │ /dashboard-  │
     │  /export     │ │ ranking  │ │  summary     │
     │  /search     │ │ /score-  │ │ /genre-      │
     │              │ │ breakdown│ │  comparison  │
     └──────┬───────┘ └────┬─────┘ └──────┬───────┘
            │              │              │
            └──────────────┼──────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Frontend      │
                  │  Next.js       │
                  │  [Agent B]     │
                  └────────────────┘
```

---

## 2. メディア処理フロー

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  ad.image_url│────→│ Playwright   │────→│ quality check │
│  (fbcdn)    │     │ render_ad    │     │ (200x200 min) │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                          ┌───────┴───────┐
                                          │               │
                                          ▼               ▼
                                   ┌──────────┐    ┌──────────┐
                                   │ S3 upload│    │ FAIL     │
                                   │ image_   │    │ retry    │
                                   │ s3_key   │    │ queue    │
                                   └────┬─────┘    └──────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │ /media/thumbnail/ │
                              │ (proxy API)       │
                              │ [Agent C]         │
                              └────────┬──────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ <img> tag         │
                              │ (fallback chain)  │
                              │ [Agent B]         │
                              │                   │
                              │ 1. proxy URL      │
                              │ 2. thumbnail_url  │
                              │ 3. image_url      │
                              │ 4. snapshot_url   │
                              │ 5. placeholder    │
                              └──────────────────┘
```

---

## 3. ヒットスコア計算フロー

```
┌──────────────────────────────────────────────────────────┐
│                    INPUT DATA                             │
├──────────────┬──────────────┬──────────────┬─────────────┤
│ days_running │ estimated_   │ is_still_    │ creative_   │
│ (Agent A)    │ spend        │ running      │ quality     │
│              │ (Agent A)    │ (Agent A)    │ (Agent D)   │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬──────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────────────────────────────────────────────────────┐
│               SCORING ENGINE [Agent C]                    │
│                                                           │
│  Signal 1: Longevity Score (0-30)                        │
│    days_running: 1-3→5, 4-7→10, 7-14→20, 14+→30         │
│                                                           │
│  Signal 2: Spend Score (0-25)                             │
│    estimated_spend: <5万→5, 5-20万→10, 20-50万→15,       │
│    50-100万→20, 100万+→25                                │
│                                                           │
│  Signal 3: Active Bonus (0-15)                            │
│    is_still_running AND days_running > 7 → +15            │
│                                                           │
│  Signal 4: Creative Score (0-15)                          │
│    creative_quality based (high→15, medium→10, low→5)     │
│                                                           │
│  Signal 5: Trend Score (0-15)                             │
│    view_count_increase / avg_increase ratio               │
│                                                           │
│  total = signal1 + signal2 + signal3 + signal4 + signal5  │
│  hit_level = total >= 70 → mega_hit                       │
│              total >= 50 → hit                             │
│              total >= 30 → rising                          │
│              else → none                                   │
└──────────────────────────────────────────────────────────┘
```

---

## 4. 通知フロー (Phase 2)

```
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│ Batch Job    │────→│ AlertEngine  │────→│ Notification  │
│ (score calc, │     │ (rule eval)  │     │ (DB insert)   │
│  crawl done) │     │ [Agent A]    │     │ [Agent C]     │
└──────────────┘     └──────────────┘     └───────┬───────┘
                                                   │
                                    ┌──────────────┼──────────┐
                                    │              │          │
                                    ▼              ▼          ▼
                           ┌──────────────┐ ┌──────────┐ ┌─────────┐
                           │ NotifyCenter │ │ Slack    │ │ Webhook │
                           │ (bell icon)  │ │ webhook  │ │ HMAC    │
                           │ [Agent B]    │ │ [Agent C]│ │[Agent C]│
                           └──────────────┘ └──────────┘ └─────────┘
```

---

## 5. ad_metadata キー所有マップ

```
ad_metadata (JSONB)
├── Agent A 所有
│   ├── days_running: number
│   ├── is_still_running: boolean
│   ├── longevity_class: string
│   ├── survival_checked_at: string
│   ├── publisher_platforms: string[]
│   ├── delivery_start_time: string
│   ├── delivery_stop_time: string
│   ├── audience_size: object
│   ├── estimated_spend: number
│   ├── estimated_views: number
│   ├── estimation_method: string
│   ├── data_quality_score: number
│   └── genre_confidence: number
│
├── Agent C 所有
│   ├── latest_hit_score: number
│   ├── latest_score_breakdown: object
│   ├── hit_level: string
│   ├── is_hit: boolean
│   ├── creative_dna: object
│   ├── hook_type: string
│   ├── cta_type: string
│   ├── offer_type: string
│   └── emotion: string
│
├── Agent D 所有
│   ├── thumbnail_fixed: boolean
│   ├── creative_quality: string
│   ├── extraction_method: string
│   ├── media_urls_backfilled: boolean
│   ├── media_quality_issues: string[]
│   ├── media_extraction_status: string
│   └── media_completeness_score: number
│
└── 共有（読み取り専用）
    ├── genre: string (via ad.genre column)
    ├── platform: string (via ad.platform column)
    └── creative_type: string (via ad.creative_type column)
```

---

## 6. DB テーブル関連図

```
┌──────────────────┐     ┌──────────────────┐
│       ad         │     │  ad_daily_metrics │
│────────────────── │     │──────────────────── │
│ id (PK)          │←────│ ad_id (FK)        │
│ ad_id (unique)   │     │ date              │
│ title            │     │ view_count        │
│ advertiser_name  │     │ like_count        │
│ genre            │     │ impressions       │
│ platform         │     │ estimated_spend   │
│ hit_score        │     │ confidence_level  │
│ trend_score      │     └──────────────────┘
│ creative_type    │
│ image_url        │     ┌──────────────────┐
│ video_url        │     │ product_ranking  │
│ thumbnail_url    │     │──────────────────── │
│ ad_metadata (J)  │←────│ ad_id (FK)        │
│ ...              │     │ rank              │
└──────────────────┘     │ hit_score         │
                         │ trend_score       │
                         │ is_hit            │
                         └──────────────────┘

┌──────────────────┐     ┌──────────────────┐
│  conversations   │     │    messages       │
│ (Phase 2)        │     │  (Phase 2)        │
│──────────────────── │     │──────────────────── │
│ id (PK)          │←────│ conversation_id   │
│ user_id          │     │ role              │
│ title            │     │ content           │
└──────────────────┘     │ intent            │
                         │ structured_data(J)│
                         └──────────────────┘

┌──────────────────┐     ┌──────────────────┐
│  alert_rules     │     │  notifications   │
│ (Phase 2)        │     │  (Phase 2)        │
│──────────────────── │     │──────────────────── │
│ id (PK)          │     │ id (PK)          │
│ name             │     │ type             │
│ condition_type   │     │ title            │
│ condition_value  │     │ message          │
│ is_active        │     │ is_read          │
└──────────────────┘     │ metadata (J)     │
                         └──────────────────┘
```
