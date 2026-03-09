#!/usr/bin/env python3
"""AI-based genre classification using AWS Bedrock (Claude Haiku 4.5).

Classifies ads that keyword matching couldn't handle ("other" genre).
Uses Claude to analyze ad title/description/advertiser and assign genre.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/classify_with_ai.py
"""
import json
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone

import boto3

DB_PATH = "vaap_local.db"
REGION = "ap-northeast-1"
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

# All valid genre slugs
VALID_GENRES = [
    "medical_weight_loss",    # 医療痩身（GLP-1, 脂肪吸引等）
    "diet_supplement",        # ダイエットサプリ・ダイエット食品
    "beauty_clinic",          # 美容クリニック・美容整形
    "skincare",               # スキンケア・化粧品
    "hair_removal",           # 脱毛
    "hair_growth_aga",        # 育毛・AGA
    "fitness",                # フィットネス・ジム・ワークアウト
    "yoga_pilates",           # ヨガ・ピラティス
    "protein_supplement",     # プロテイン
    "health_food",            # 健康食品・サプリメント
    "ec_shopping",            # EC通販・ショッピング
    "app",                    # アプリ（マッチング、ユーティリティ等）
    "finance_investment",     # 金融・投資・保険
    "education_school",       # 教育・スクール・資格
    "real_estate",            # 不動産
    "jobs_recruitment",       # 転職・求人
    "short_drama",            # ショートドラマ・ミニドラマアプリ
    "manga_webtoon",          # マンガ・ウェブトゥーン
    "gaming_entertainment",   # ゲーム・VR・エンタメ
    "other",                  # 本当に分類不能なもの
]

GENRE_DISPLAY_JP = {
    "medical_weight_loss": "\u533b\u7642\u75e9\u8eab",
    "diet_supplement": "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",
    "beauty_clinic": "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af",
    "skincare": "\u30b9\u30ad\u30f3\u30b1\u30a2",
    "hair_removal": "\u8131\u6bdb",
    "hair_growth_aga": "\u80b2\u6bdb\u30fbAGA",
    "fitness": "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",
    "yoga_pilates": "\u30e8\u30ac\u30fb\u30d4\u30e9\u30c6\u30a3\u30b9",
    "protein_supplement": "\u30d7\u30ed\u30c6\u30a4\u30f3",
    "health_food": "\u5065\u5eb7\u98df\u54c1",
    "ec_shopping": "EC\u901a\u8ca9",
    "app": "\u30a2\u30d7\u30ea",
    "finance_investment": "\u91d1\u878d\u30fb\u6295\u8cc7",
    "education_school": "\u6559\u80b2\u30fb\u30b9\u30af\u30fc\u30eb",
    "real_estate": "\u4e0d\u52d5\u7523",
    "jobs_recruitment": "\u8ee2\u8077\u30fb\u6c42\u4eba",
    "short_drama": "\u30b7\u30e7\u30fc\u30c8\u30c9\u30e9\u30de",
    "manga_webtoon": "\u30de\u30f3\u30ac\u30fb\u30a6\u30a7\u30d6\u30c8\u30a5\u30fc\u30f3",
    "gaming_entertainment": "\u30b2\u30fc\u30e0\u30fb\u30a8\u30f3\u30bf\u30e1",
    "other": "\u305d\u306e\u4ed6",
}

SYSTEM_PROMPT = """You are an ad genre classifier for Japanese advertising market analysis.

Given an ad's title, description, advertiser name, and destination URL, classify it into exactly ONE genre.

Valid genres:
- medical_weight_loss: Medical weight loss (GLP-1, liposuction, fat freezing, medical diet clinics)
- diet_supplement: Diet supplements, diet foods, meal replacement
- beauty_clinic: Beauty clinics, cosmetic surgery, anti-aging treatments
- skincare: Skincare products, cosmetics, makeup
- hair_removal: Hair removal (laser, IPL, salon)
- hair_growth_aga: Hair growth, AGA treatment, hair loss
- fitness: Fitness, gym, workout, personal training, exercise apps
- yoga_pilates: Yoga, pilates, stretching, meditation
- protein_supplement: Protein supplements
- health_food: Health foods, supplements, vitamins
- ec_shopping: E-commerce, online shopping, fashion
- app: Mobile apps (utility, dating, tracking, tools)
- finance_investment: Finance, investment, insurance, loans, credit cards
- education_school: Education, online courses, language learning, schools
- real_estate: Real estate, apartments, housing
- jobs_recruitment: Jobs, recruitment, career change
- short_drama: Short drama apps, mini drama, drama streaming (DramaBox, DramaWave, Flick, etc.)
- manga_webtoon: Manga, webtoon, comics
- gaming_entertainment: Games, VR, entertainment devices
- other: ONLY if truly unclassifiable (removed ads, spam, completely irrelevant)

IMPORTANT:
- Ads about drama/stories with emotional titles and apps like DramaBox/Flick/Reels → short_drama
- Chinese drama/romance/revenge stories → short_drama
- "This content was removed" → other
- Ads with only "今すぐ見る" (Watch now) with drama-like context → short_drama
- Phone tracker/location apps → app
- Blood pressure/health monitoring apps → app
- Music production tools → education_school
- VR headsets (Meta Quest, Oculus) → gaming_entertainment

Respond with ONLY the genre slug, nothing else."""


def classify_batch_with_bedrock(client, ads_batch):
    """Classify a batch of ads using Bedrock Claude Haiku."""
    results = []

    for ad in ads_batch:
        ad_id, title, desc, adv, dest_url = ad

        user_msg = f"""Classify this ad:
Title: {title or '-'}
Description: {(desc or '-')[:300]}
Advertiser: {adv or '-'}
URL: {dest_url or '-'}"""

        try:
            response = client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 50,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": user_msg}
                    ],
                    "temperature": 0.0,
                }),
            )

            body = json.loads(response["body"].read())
            genre = body["content"][0]["text"].strip().lower()

            # Validate genre
            if genre not in VALID_GENRES:
                # Try to find closest match
                for valid in VALID_GENRES:
                    if valid in genre:
                        genre = valid
                        break
                else:
                    genre = "other"

            results.append((ad_id, genre))

        except Exception as e:
            print(f"  ERROR ad_id={ad_id}: {e}")
            results.append((ad_id, "other"))
            time.sleep(1)  # back off on error

    return results


def main():
    print("=" * 60)
    print("AI Genre Classification (AWS Bedrock - Claude Haiku 4.5)")
    print(f"Region: {REGION}")
    print(f"Model:  {MODEL_ID}")
    print("=" * 60)

    # Get "other" ads from DB
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, description, advertiser_name, destination_url, metadata "
        "FROM ads WHERE json_extract(metadata, '$.fine_genre_en') = 'other'"
    )
    rows = cur.fetchall()
    total = len(rows)
    print(f"\nAds to classify (currently 'other'): {total}")

    if total == 0:
        print("No 'other' ads to classify. Done!")
        conn.close()
        return

    # Prepare batch
    ads_batch = [(r[0], r[1], r[2], r[3], r[4]) for r in rows]
    meta_map = {}
    for r in rows:
        meta_map[r[0]] = json.loads(r[5]) if r[5] else {}

    # Initialize Bedrock client
    client = boto3.client("bedrock-runtime", region_name=REGION)
    print(f"Bedrock client initialized.")

    # Classify
    print(f"\nClassifying {total} ads with AI...")
    genre_counter = Counter()
    now = datetime.now(timezone.utc).isoformat()
    updates = []

    for i, ad in enumerate(ads_batch):
        ad_id = ad[0]

        # Classify single ad
        results = classify_batch_with_bedrock(client, [ad])

        if results:
            _, genre = results[0]
        else:
            genre = "other"

        jp_label = GENRE_DISPLAY_JP.get(genre, genre)
        meta = meta_map[ad_id]
        meta["fine_genre"] = jp_label
        meta["fine_genre_en"] = genre
        meta["fine_genre_classified_at"] = now
        meta["fine_genre_method"] = "ai_bedrock"
        updates.append((json.dumps(meta, ensure_ascii=False), now, ad_id))
        genre_counter[genre] += 1

        if (i + 1) % 10 == 0 or i == total - 1:
            print(f"  Progress: {i+1}/{total} ({(i+1)/total*100:.0f}%)")

        # Rate limiting: ~5 requests/sec for Haiku
        time.sleep(0.2)

    # Write results
    cur.executemany(
        "UPDATE ads SET metadata = ?, updated_at = ? WHERE id = ?",
        updates,
    )
    conn.commit()
    conn.close()

    # Report
    print(f"\n--- AI Classification Results ({total} ads) ---")
    for slug, count in sorted(genre_counter.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {slug:<25s} {count:>4d} ({pct:>5.1f}%)")

    still_other = genre_counter.get("other", 0)
    reclassified = total - still_other
    print(f"\n  Reclassified by AI: {reclassified} ({reclassified/total*100:.1f}%)")
    print(f"  Still 'other':      {still_other} ({still_other/total*100:.1f}%)")
    print(f"\nDone!")


if __name__ == "__main__":
    main()
