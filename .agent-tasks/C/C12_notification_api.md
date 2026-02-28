# Agent C Task: Alerts & Bookmarks API

## Goal
Users need to save favorite ads, set alerts for new hits, and bookmark interesting creatives.

## What to do

### 1. Bookmarks API
Add to rankings.py:

`POST /rankings/bookmarks` - bookmark an ad
- Body: { ad_id: int, note?: str, tags?: list[str] }
- Store in ad_metadata["bookmarked"] = true, ad_metadata["bookmark_note"], ad_metadata["bookmark_tags"]

`GET /rankings/bookmarks` - list all bookmarked ads
- Full ad details with resolved URLs
- Filter by tags
- Sort by bookmark date

`DELETE /rankings/bookmarks/{ad_id}` - remove bookmark

### 2. Collections API
`POST /rankings/collections` - create a collection (folder)
- Body: { name: str, description?: str }
- Store collections in a simple JSON file: backend/data/collections.json

`GET /rankings/collections` - list all collections

`POST /rankings/collections/{collection_id}/ads` - add ad to collection
- Body: { ad_id: int }

`GET /rankings/collections/{collection_id}` - get collection with all ads

### 3. Smart alerts (computed)
`GET /rankings/alerts` - get current alerts
- New high-score ads (score > 80) found in last 24h
- Trend changes (patterns rising/falling)
- New ads from bookmarked advertisers
- Computed on-the-fly, no background worker needed

### 4. Activity log
`GET /rankings/activity` - recent system activity
- Recent crawls, new ads found, score updates
- Based on CrawlJob table + ad created_at timestamps

## Constraints
- Only modify rankings.py
- For collections, use a JSON file (backend/data/collections.json) - create dir if needed
- flag_modified for ad_metadata bookmark changes
