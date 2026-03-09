import { expect, test, type Page } from "@playwright/test";
import { primeAppState } from "./helpers/appState";

const hitAdsHeading = (page: Page) => page.getByRole("heading", { name: "ヒット広告分析", exact: true });
const detailModal = (page: Page) => page.locator("div.fixed.inset-0.z-50").first();

const hitAdsPayload = {
  total: 3,
  items: [
    {
      rank: 1,
      ad_id: 701,
      product_name: "正常LP広告",
      advertiser_name: "広告主A",
      genre: "beauty",
      platform: "facebook",
      view_increase: 1400,
      spend_increase: 18000,
      cumulative_views: 24000,
      cumulative_spend: 210000,
      is_hit: true,
      hit_score: 83,
      trend_score: 77,
      rank_change: 2,
      previous_rank: 3,
      thumbnail: "https://example.com/thumb-701.jpg",
      duration_seconds: 15,
      image_url: "https://example.com/image-701.jpg",
      snapshot_url: "https://example.com/snap-701.jpg",
      destination_url: "https://go.example-short.com/ad701",
      destination_type: "記事LP",
      like_count: 120,
      published_date: "2026-03-07T00:00:00Z",
      management_id: "N00701",
      ad_url: "https://example.com/ad/701",
      description: "正常LP広告の説明",
      title: "正常LP広告",
      creative_type: "video",
      estimation_method: "audience_based",
      metric_source: "api",
      creative_source: "api",
      lp_source: "httpx",
      metric_status: "real",
      creative_status: "real",
      freshness_status: "fresh",
      last_meta_success_at: "2026-03-08T09:15:00Z",
      meta_quality_state: "real",
      language: "ja",
      language_source: "bedrock",
      media_status: {
        viewable: true,
        downloadable: true,
        has_lp: true,
        primary_type: "video",
        missing_reasons: [],
      },
    },
    {
      rank: 2,
      ad_id: 702,
      product_name: "snapshot only 広告",
      advertiser_name: "広告主B",
      genre: "beauty",
      platform: "instagram",
      view_increase: 640,
      spend_increase: 8200,
      cumulative_views: 11000,
      cumulative_spend: 92000,
      is_hit: true,
      hit_score: 61,
      trend_score: 55,
      rank_change: null,
      previous_rank: null,
      thumbnail: "",
      duration_seconds: 6,
      image_url: "",
      snapshot_url: "https://example.com/snap-702.jpg",
      destination_url: "",
      destination_type: "",
      like_count: 48,
      published_date: "2026-03-06T00:00:00Z",
      management_id: "N00702",
      ad_url: "https://example.com/ad/702",
      description: "snapshot only 広告の説明",
      title: "snapshot only 広告",
      creative_type: "video",
      estimation_method: "modeled",
      metric_source: "estimated",
      creative_source: "playwright_render_ad",
      lp_source: "missing",
      metric_status: "estimated",
      creative_status: "estimated",
      freshness_status: "stale",
      last_meta_success_at: "2026-03-01T08:00:00Z",
      meta_quality_state: "stale",
      meta_recovery_reason: "detail_enrich_failed",
      language: "en",
      language_source: "bedrock",
      exclude_from_analysis: true,
      exclude_reason: "non_japanese",
      media_status: {
        viewable: true,
        downloadable: false,
        has_lp: false,
        primary_type: "snapshot",
        missing_reasons: ["snapshot_only", "lp_unresolved"],
      },
    },
    {
      rank: 3,
      ad_id: 703,
      product_name: "欠損数値広告",
      advertiser_name: "広告主C",
      genre: "beauty",
      platform: "facebook",
      view_increase: 0,
      spend_increase: 0,
      cumulative_views: 0,
      cumulative_spend: 0,
      is_hit: true,
      hit_score: 52,
      trend_score: 0,
      rank_change: null,
      previous_rank: null,
      thumbnail: "https://example.com/thumb-703.jpg",
      duration_seconds: 10,
      image_url: "https://example.com/image-703.jpg",
      snapshot_url: "",
      destination_url: "",
      destination_type: "",
      like_count: 0,
      published_date: "2026-03-05T00:00:00Z",
      management_id: "N00703",
      ad_url: "https://example.com/ad/703",
      description: "欠損数値広告の説明",
      title: "欠損数値広告",
      creative_type: "image",
      metric_source: "missing",
      creative_source: "api",
      lp_source: "missing",
      metric_status: "missing",
      creative_status: "real",
      freshness_status: "missing",
      meta_quality_state: "missing",
      language: "",
      media_status: {
        viewable: true,
        downloadable: true,
        has_lp: false,
        primary_type: "image",
        missing_reasons: ["missing_lp"],
      },
    },
  ],
};

async function installCreativeLibraryMocks(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "healthy", database: "ok" }),
    });
  });

  await page.route("**/api/v1/rankings/hit-ads**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(hitAdsPayload),
    });
  });

  await page.route("**/api/v1/rankings/products**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });

  await page.route("**/api/v1/rankings/genre-summary**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ genres: [{ genre: "beauty", ad_count: 3, advertiser_count: 3, total_views: 35000, total_spend: 302000 }] }),
    });
  });

  await page.route("**/api/v1/rankings/score-distribution**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ distribution: [{ bucket: "50-69", count: 2 }, { bucket: "80-89", count: 1 }], mean: 65, median: 61, hit_count: 1, mega_hit_count: 1 }),
    });
  });

  await page.route("**/api/v1/rankings/dashboard-summary**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ mega_hit_count: 1, hit_count: 1, total_ads: 3, active_ads: 3, avg_score: 65, top_genre: "beauty", top_creative_type: "video" }),
    });
  });

  await page.route("**/api/v1/rankings/genre-comparison**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ genres: [{ genre: "beauty", ad_count: 3, avg_score: 65, hit_rate: 100 }] }),
    });
  });

  await page.route("**/api/v1/rankings/score-breakdown/701", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ signals: { longevity: { score: 18, max: 40 }, creative: { score: 9, max: 10, detail: "サムネ完走率が高い" } } }),
    });
  });

  await page.route("**/api/v1/rankings/ad360/701", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 701,
        sections: {
          core: { data: { ad_id: 701, title: "正常LP広告", advertiser_name: "広告主A" }, missing_fields: [] },
          creative: { data: { creative_type: "video", media_status: { viewable: true, downloadable: true } }, missing_fields: [] },
          text: { data: { description: "正常LP広告の説明", hook_text: "実感が早い" }, missing_fields: [] },
          analysis: { data: { hit_score: 83, evidence_terms: ["実感", "継続"], hit_drivers: ["hit_score", "lp_quality"] }, missing_fields: [] },
          lp: {
            data: {
              url: "https://go.example-short.com/ad701",
              resolved_url: "https://landing.example.com/final",
              final_url: "https://landing.example.com/final",
              source_domain: "go.example-short.com",
              domain: "landing.example.com",
              destination_type: "記事LP",
              lp_status: "redirect",
              lp_score: 78,
              trust_score: 81,
              structure_summary: "比較導入から購入CTAへ接続する構成",
            },
            missing_fields: [],
          },
          quality: { data: { extract_quality_score: 74, needs_media_retry: true, media_status: { viewable: true, downloadable: true }, quality_flags: { has_video: true } }, missing_fields: [] },
        },
      }),
    });
  });

  await page.route("**/api/v1/rankings/score-breakdown/703", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ signals: { longevity: { score: 8, max: 40 } } }),
    });
  });

  await page.route("**/api/v1/rankings/ad360/703", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 703,
        sections: {
          core: { data: { ad_id: 703, title: "欠損数値広告", advertiser_name: "広告主C" }, missing_fields: [] },
          creative: { data: { creative_type: "image", media_status: { viewable: true, downloadable: true } }, missing_fields: [] },
          text: { data: { description: "欠損数値広告の説明" }, missing_fields: [] },
          analysis: { data: { hit_score: 52, evidence_terms: [] }, missing_fields: [] },
          lp: { data: { url: "", lp_status: "unresolved", lp_score: null }, missing_fields: ["url", "domain", "lp_score"] },
          quality: { data: { needs_media_retry: false, media_status: { viewable: true, downloadable: true, has_lp: false } }, missing_fields: ["extract_quality_score"] },
        },
      }),
    });
  });

  await page.route("**/api/v1/ads/701/media", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 701,
        image_url: "https://example.com/image-701.jpg",
        video_url: "https://example.com/video-701.mp4",
        snapshot_url: "https://example.com/snap-701.jpg",
        download_url: "/api/v1/media/download/701",
        media_status: {
          viewable: true,
          downloadable: true,
          has_lp: true,
          primary_type: "video",
          missing_reasons: [],
        },
        lp_info: {
          destination_url: "https://go.example-short.com/ad701",
          resolved_url: "https://landing.example.com/final",
          domain: "go.example-short.com",
          final_domain: "landing.example.com",
          destination_type: "記事LP",
          lp_status: "redirect",
          lp_score: 78,
          http_status: 302,
          has_lp: true,
        },
      }),
    });
  });

  await page.route("**/api/v1/ads/703/media", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 703,
        image_url: "https://example.com/image-703.jpg",
        snapshot_url: "",
        download_url: "/api/v1/media/download/703",
        media_status: {
          viewable: true,
          downloadable: true,
          has_lp: false,
          primary_type: "image",
          missing_reasons: ["missing_lp"],
        },
        lp_info: {
          destination_url: "",
          resolved_url: "",
          domain: "",
          final_domain: "",
          destination_type: "",
          lp_status: "unresolved",
          lp_score: null,
          has_lp: false,
        },
      }),
    });
  });

  await page.route("**/api/v1/settings/meta/token-info", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        has_token: true,
        token_source: "db",
        runtime_source: "db",
        source_priority: ["db", "env", "missing"],
        fallback_used: false,
        fallback_reason: null,
        is_valid: true,
        expires_at: 4102444800,
        days_remaining: 30,
        is_expiring: false,
        scopes: ["ads_read"],
        last_validation_error: null,
        message: "Meta token healthy",
      }),
    });
  });

  await page.route("**/api/v1/media/thumbnail/**", async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });

  await page.route("**/api/v1/media/video/**", async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });

  await page.route("**/api/v1/media/bulk-download", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        download_url: "https://example.com/downloads/creative-library.zip",
        file_count: 1,
        total_size_bytes: 1572864,
        zip_filename: "creative-library.zip",
        skipped_ids: [],
        skipped_reason_code: null,
      }),
    });
  });

  await page.route("**/api/v1/data-quality/creative-library-audit**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        creative_library_audit: {
          summary: {
            total_ads: 3,
            creative_viewable_rate: 1,
            creative_downloadable_rate: 0.67,
            lp_present_rate: 0.33,
            lp_resolved_rate: 0.33,
            missing_media_count: 1,
            missing_lp_count: 2,
          },
          platform_breakdown: [
            { label: "facebook", total_ads: 2, missing_media_count: 0, download_unavailable_count: 0, lp_unresolved_count: 1 },
            { label: "instagram", total_ads: 1, missing_media_count: 1, download_unavailable_count: 1, lp_unresolved_count: 1 },
          ],
          genre_breakdown: [
            { label: "beauty", total_ads: 3, missing_media_count: 1, download_unavailable_count: 1, lp_unresolved_count: 2 },
          ],
          priority_recovery_ads: [
            {
              ad_id: 702,
              title: "snapshot only 広告",
              advertiser_name: "広告主B",
              platform: "instagram",
              genre: "beauty",
              priority_score: 88,
              failure_reason_codes: ["not_downloadable", "lp_unresolved"],
              needs_download_recovery: true,
              needs_lp_resolution: true,
            },
          ],
          creative_library_daily_report: {
            top_regressions: [
              {
                ad_id: 702,
                title: "snapshot only 広告",
                platform: "instagram",
                genre: "beauty",
                delta_score: -2,
                direction: "regressed",
                failure_reason_codes: ["not_downloadable", "lp_unresolved"],
              },
            ],
            top_recoveries: [
              {
                ad_id: 701,
                title: "正常LP広告",
                platform: "facebook",
                genre: "beauty",
                delta_score: 2,
                direction: "recovered",
              },
            ],
            worsening_segments: [
              { segment_type: "platform", label: "instagram", metric: "downloadable", delta: -1 },
            ],
          },
        },
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page, { disableWindowOpen: true });
  await installCreativeLibraryMocks(page);
});

test.describe("Creative Library Smoke @smoke", () => {
  test("pins real estimated missing and stale numeric provenance states", async ({ page }) => {
    await page.goto("/?view=hit-ads");
    await expect(hitAdsHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("数値 provenance")).toBeVisible();
    await expect(page.getByText("missing_numeric_count > 0 / backfill待ち。")).toBeVisible();

    await page.getByRole("button", { name: "テーブル", exact: true }).click();
    await expect(page.locator("tr", { hasText: "正常LP広告" }).getByText("実測").first()).toBeVisible();
    await expect(page.locator("tr", { hasText: "欠損数値広告" }).getByText("欠損").first()).toBeVisible();

    await page.getByText("正常LP広告").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(detailModal(page).getByText("実測").first()).toBeVisible();
    await expect(detailModal(page).getByText("推定").first()).toBeVisible();
    await expect(detailModal(page).getByText("stale").first()).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByText("欠損数値広告").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(detailModal(page).getByText("欠損").first()).toBeVisible();
  });

  test("shows snapshot-only and lp-unresolved empty states in gallery and displays LP trust in detail", async ({ page }) => {
    await page.goto("/?view=hit-ads");
    await expect(hitAdsHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("クリエイティブライブラリ回帰監視")).toBeVisible();
    await expect(page.getByText("悪化上位")).toBeVisible();
    await expect(page.getByText("DL可")).toBeVisible();
    await page.getByRole("button", { name: "ギャラリー", exact: true }).click();
    await page.getByRole("button", { name: /復旧待ち 2/ }).click();
    await expect(page.getByText("snapshot only 広告").first()).toBeVisible();

    await expect(page.getByText("snapshot only", { exact: false }).first()).toBeVisible();
    await expect(page.getByText("LP未解決").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "再取得", exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "全て", exact: true }).first().click();

    await page.getByText("正常LP広告").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("LP信頼")).toBeVisible();
    await expect(page.getByText("最終遷移先", { exact: true })).toBeVisible();
    await expect(page.getByText("https://landing.example.com/final").first()).toBeVisible();
    await expect(page.getByText("domain mismatch")).toBeVisible();
    await expect(page.getByRole("button", { name: "最終LPを見る" })).toBeEnabled();
  });

  test("shows bulk-download result summary after zip creation", async ({ page }) => {
    await page.goto("/?view=hit-ads");
    await expect(hitAdsHeading(page)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: "テーブル", exact: true }).click();
    await page.locator("tbody input[type='checkbox']").first().check();
    await page.getByRole("button", { name: "1件ZIP", exact: true }).click();

    await expect(page.getByText("一括ダウンロード結果")).toBeVisible();
    await expect(page.getByText("creative-library.zip")).toBeVisible();
    await expect(page.getByText("1件をZIP化")).toBeVisible();
  });

  test("shows Meta provenance, new badge, and excluded warning in ad detail", async ({ page }) => {
    await page.goto("/?view=hit-ads");
    await expect(hitAdsHeading(page)).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "カード", exact: true }).click();
    await expect(page.getByText("NEW").first()).toBeVisible();
    await expect(page.getByText("metrics API").first()).toBeVisible();
    await page.getByText("snapshot only 広告").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(detailModal(page).getByText("Meta品質 / Provenance")).toBeVisible();
    await expect(detailModal(page).getByText("token db")).toBeVisible();
    await expect(detailModal(page).getByText("snapshot only / lp missing / detail enrich failed")).toBeVisible();
    await expect(detailModal(page).getByText("recovery reason: detail enrich failed")).toBeVisible();
    await expect(detailModal(page).getByText("non-JP").first()).toBeVisible();
    await expect(detailModal(page).getByText("AI判定").first()).toBeVisible();
    await expect(detailModal(page).getByText("除外").first()).toBeVisible();
    await expect(detailModal(page).getByText("exclude_from_analysis=true / non_japanese")).toBeVisible();
  });
});
