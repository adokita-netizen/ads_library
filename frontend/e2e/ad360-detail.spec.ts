import { expect, test, type Page } from "@playwright/test";
import { primeAppState } from "./helpers/appState";

const heading = (page: Page) => page.getByRole("heading", { name: "PRO DATABASE", exact: true }).first();
const rankingTable = (page: Page) => page.locator('table[aria-label="広告ランキング"]').first();
const detailModal = (page: Page) => page.locator("div.fixed.inset-0.z-50").first();

async function installAd360Mocks(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "healthy", database: "ok" }) });
  });

  await page.route("**/api/v1/rankings/genre-master**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ genres: [{ genre: "美容・コスメ" }] }) });
  });

  await page.route("**/api/v1/rankings/search-collections**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ collections: [] }) });
  });

  await page.route("**/api/v1/rankings/pro-ranking**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [{
          ad_id: 501,
          rank: 1,
          title: "Ad360広告A",
          advertiser_name: "広告主A",
          fine_genre: "美容・コスメ",
          hit_score: 82,
          cumulative_views: 12000,
          estimated_spend_increase_jpy: 120000,
          duration_seconds: 15,
          view_increase: 800,
          spend_increase: 9000,
          platform: "facebook",
          is_above_hit_line: true,
          language: "ja",
          language_source: "bedrock",
          topic_label: "GLP-1",
          topic_confidence: 0.91,
          classification_source: "bedrock",
          priority: "high",
          priority_score: 92,
          review_required: true,
          review_reason: "low_confidence",
        }, {
          ad_id: 502,
          rank: 2,
          title: "Excluded広告",
          advertiser_name: "広告主B",
          fine_genre: "美容・コスメ",
          hit_score: 60,
          cumulative_views: 9000,
          estimated_spend_increase_jpy: 80000,
          duration_seconds: 12,
          view_increase: 500,
          spend_increase: 6000,
          platform: "instagram",
          is_above_hit_line: false,
          language: "en",
          language_source: "bedrock",
          exclude_from_analysis: true,
          exclude_reason: "non_japanese",
          topic_label: "海外訴求",
          topic_confidence: 0.88,
          classification_source: "manual_review",
          priority: "high",
          priority_score: 85,
          review_required: true,
          review_reason: "manual_review_queue",
        }, {
          ad_id: 503,
          rank: 3,
          title: "Unknown広告",
          advertiser_name: "広告主C",
          fine_genre: "美容・コスメ",
          hit_score: 55,
          cumulative_views: 7000,
          estimated_spend_increase_jpy: 50000,
          duration_seconds: 10,
          view_increase: 300,
          spend_increase: 4000,
          platform: "facebook",
          is_above_hit_line: false,
          topic_label: "汎用訴求",
          topic_confidence: 0.42,
          classification_source: "rule_engine",
          priority: "medium",
          priority_score: 60,
          review_required: false,
        }, {
          ad_id: 504,
          rank: 4,
          title: "NonJP広告",
          advertiser_name: "広告主D",
          fine_genre: "美容・コスメ",
          hit_score: 50,
          cumulative_views: 6500,
          estimated_spend_increase_jpy: 45000,
          duration_seconds: 9,
          view_increase: 250,
          spend_increase: 3500,
          platform: "facebook",
          is_above_hit_line: false,
          language: "en",
          language_source: "bedrock",
          topic_label: "Generic",
          topic_confidence: 0.72,
          classification_source: "bedrock",
          priority: "low",
          priority_score: 25,
          review_required: false,
        }],
        total: 4,
        page: 1,
        per_page: 50,
        total_pages: 1,
        fine_genres: ["美容・コスメ"],
        hit_line_threshold: 10000,
      }),
    });
  });

  await page.route("**/api/v1/ads/501**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 501,
        external_id: "AD-501",
        product_name: "Ad360広告A",
        advertiser_name: "広告主A",
        category: "美容・コスメ",
        cumulative_spend: 120000,
        cumulative_views: 12000,
        published_date: "2026-03-07T00:00:00Z",
        duration_seconds: 15,
        platform: "facebook",
        destination_type: "lead_gen",
        destination_url: "https://example.com/lp",
        image_url: "https://example.com/thumb.jpg",
        video_url: "",
        snapshot_url: "https://example.com/snap.jpg",
        creative_type: "video",
        language: "ja",
        language_source: "bedrock",
        topic_label: "GLP-1",
        topic_confidence: 0.91,
        classification_source: "bedrock",
        priority: "high",
        priority_score: 92,
        review_required: true,
        review_reason: "low_confidence",
      }),
    });
  });

  await page.route("**/api/v1/ads/502**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 502,
        external_id: "AD-502",
        product_name: "Excluded広告",
        advertiser_name: "広告主B",
        category: "美容・コスメ",
        cumulative_spend: 80000,
        cumulative_views: 9000,
        published_date: "2026-03-06T00:00:00Z",
        duration_seconds: 12,
        platform: "instagram",
        destination_type: "lead_gen",
        destination_url: "https://example.com/non-jp",
        image_url: "https://example.com/nonjp.jpg",
        creative_type: "image",
        language: "en",
        language_source: "bedrock",
        exclude_from_analysis: true,
        exclude_reason: "non_japanese",
        topic_label: "海外訴求",
        topic_confidence: 0.88,
        classification_source: "manual_review",
        priority: "high",
        priority_score: 85,
        review_required: true,
        review_reason: "manual_review_queue",
      }),
    });
  });

  await page.route("**/api/v1/rankings/score-breakdown/501", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ signals: { longevity: { score: 18, max: 40 }, creative: { score: 8, max: 10, detail: "動画完走率が高い" } } }),
    });
  });

  await page.route("**/api/v1/rankings/ad360/501", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 501,
        sections: {
          core: { data: { ad_id: 501, title: "Ad360広告A", advertiser_name: "広告主A", platform: "facebook", genre: "美容・コスメ", first_seen_at: "2026-03-07T00:00:00Z", last_seen_at: "2026-03-08T00:00:00Z" }, missing_fields: [] },
          creative: { data: { creative_type: "video", media_status: "partial", extract_source: "snapshot_fallback", thumbnail_url: "https://example.com/thumb.jpg" }, missing_fields: ["video_url"] },
          text: { data: { description: "糖質ケアの動画広告", hook_text: "3秒で惹きつける", cta_text: "詳しく見る", ocr_texts: ["糖質", "体型"], transcript: "" }, missing_fields: ["transcript"] },
          analysis: { data: { hit_score: 82, hit_level: "hit", topic_label: "GLP-1", topic_confidence: 0.76, matched_terms: ["GLP-1", "糖質"], evidence_terms: ["GLP-1", "糖質"], hit_drivers: ["hit_score", "video_creative"], classification_source: "bedrock", priority: "high", priority_score: 92, review_required: true, review_reason: "low_confidence" }, missing_fields: [] },
          lp: { data: { domain: "example.com", title: "糖質ケアLP", lp_type: "lead_gen", status: "completed", lp_score: 74, structure_summary: "訴求からCTAまで一直線のLPです。", url: "https://short.example.com/lp", final_url: "https://example.com/lp" }, missing_fields: [] },
          quality: { data: { extract_quality_score: 34, needs_media_retry: true, media_status: "partial", topic_confidence: 0.76, quality_flags: { has_image: false, has_video: false, has_ocr: true, has_transcript: false } }, missing_fields: ["extract_quality_score"] },
        },
      }),
    });
  });

  await page.route("**/api/v1/rankings/ad360/502", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 502,
        sections: {
          core: { data: { ad_id: 502, title: "Excluded広告", advertiser_name: "広告主B", platform: "instagram", genre: "美容・コスメ" }, missing_fields: [] },
          creative: { data: { creative_type: "image", media_status: "ok" }, missing_fields: [] },
          text: { data: { description: "foreign language ad" }, missing_fields: [] },
          analysis: { data: { hit_score: 60, topic_label: "海外訴求", topic_confidence: 0.88, classification_source: "manual_review", priority: "high", priority_score: 85, review_required: true, review_reason: "manual_review_queue" }, missing_fields: [] },
          lp: { data: { domain: "example.com", title: "Foreign LP", status: "completed", lp_score: 40, url: "https://example.com/non-jp", final_url: "https://example.com/non-jp" }, missing_fields: [] },
          quality: { data: { extract_quality_score: 70, media_status: "ok" }, missing_fields: [] },
        },
      }),
    });
  });

  await page.route("**/api/v1/rankings/classify-topic", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ confidence: 0.91, evidence_terms: ["GLP-1", "糖質", "代謝"], hit_drivers: ["hit_score", "destination_quality"] }) });
  });

  await page.route("**/api/v1/rankings/dictionary/suggest", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ candidate_terms: [{ topic_label: "glp-1", term: "代謝", confidence: 0.88 }] }) });
  });

  await page.route("**/api/v1/rankings/knowledge/rebuild", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
  });

  await page.route("**/api/v1/rankings/meta-extraction/501/retry", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ dispatched: true }) });
  });

  await page.route("**/api/v1/lp-analysis/crawl", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ started: true }) });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installAd360Mocks(page);
});

test.describe("Ad360 Detail View", () => {
  test("supports JP only filtering and shows jp non-jp unknown excluded states", async ({ page }) => {
    await page.goto("/?view=pro-database");
    await expect(heading(page)).toBeVisible({ timeout: 15000 });
    await expect(rankingTable(page).getByText("Ad360広告A")).toBeVisible();
    await expect(rankingTable(page).getByText("Excluded広告")).toBeHidden();

    await page.getByRole("checkbox", { name: "JP only" }).click();
    await expect(rankingTable(page).getByText("Excluded広告")).toBeVisible();
    await expect(rankingTable(page).getByText("Unknown広告")).toBeVisible();
    await expect(rankingTable(page).getByText("NonJP広告")).toBeVisible();
    await expect(rankingTable(page).getByText("JP").first()).toBeVisible();
    await expect(rankingTable(page).getByText("non-JP").first()).toBeVisible();
    await expect(rankingTable(page).getByText("未判定").first()).toBeVisible();
    await expect(rankingTable(page).getByText("AI判定").first()).toBeVisible();
    await expect(rankingTable(page).getByText("除外").first()).toBeVisible();

    await rankingTable(page).getByText("Excluded広告").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(detailModal(page).getByText("non-JP").first()).toBeVisible();
    await expect(detailModal(page).getByText("AI判定").first()).toBeVisible();
    await expect(detailModal(page).getByText("exclude_from_analysis=true / non_japanese")).toBeVisible();
    await expect(detailModal(page).getByText("manual").first()).toBeVisible();
    await expect(detailModal(page).getByText("high").first()).toBeVisible();
    await expect(detailModal(page).getByText("review_reason").first()).toBeVisible();
    await expect(detailModal(page).getByText("confidence_band").first()).toBeVisible();
  });

  test("supports operation view and shows high priority manual review ai and rule-only states", async ({ page }) => {
    await page.goto("/?view=pro-database");
    await expect(heading(page)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: "運用ビュー" }).click();
    await expect(rankingTable(page).getByText("Ad360広告A")).toBeVisible();
    await expect(rankingTable(page).getByText("Excluded広告")).toBeHidden();
    await expect(rankingTable(page).getByText("Unknown広告")).toBeHidden();

    await page.getByRole("button", { name: "運用ビュー" }).click();
    await page.getByRole("checkbox", { name: "JP only" }).click();
    await expect(rankingTable(page).getByText("Excluded広告")).toBeVisible();
    await expect(rankingTable(page).getByText("Unknown広告")).toBeHidden();
    await expect(rankingTable(page).getByText("NonJP広告")).toBeHidden();
    await expect(rankingTable(page).getByText("manual").first()).toBeVisible();
    await expect(rankingTable(page).getByText("AI").first()).toBeVisible();

    await page.getByRole("checkbox", { name: "review required" }).uncheck();
    await page.locator('select[title="priority絞り込み"]').selectOption("all");
    await expect(rankingTable(page).getByText("Unknown広告")).toBeVisible();
    await expect(rankingTable(page).getByText("rule").first()).toBeVisible();
  });

  test("shows unified detail sections and missing-field guidance", async ({ page }) => {
    await page.goto("/?view=pro-database");
    await expect(heading(page)).toBeVisible({ timeout: 15000 });
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });
    await rankingTable(page).getByText("Ad360広告A").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Ad360 Unified Detail")).toBeVisible();
    await expect(page.getByText("LP信頼")).toBeVisible();
    await expect(page.getByText("最終遷移先")).toBeVisible();
    await expect(page.getByRole("link", { name: "https://example.com/lp" })).toBeVisible();
    await expect(page.getByText("判定根拠語")).toBeVisible();
    await expect(page.getByText("訴求からCTAまで一直線のLPです。").first()).toBeVisible();
    await expect(page.getByText("video url")).toBeVisible();
    await expect(page.getByText("extract quality score")).toBeVisible();
    await expect(detailModal(page).getByText("実測").first()).toBeVisible();
    await expect(detailModal(page).getByText("推定").first()).toBeVisible();
    await expect(detailModal(page).getByText("欠損").first()).toBeVisible();
  });

  test("dispatches reclassify, dictionary, and retry actions from the same modal", async ({ page }) => {
    let classifyCalls = 0;
    let dictionaryCalls = 0;
    let recrawlCalls = 0;
    let retryCalls = 0;

    await page.unroute("**/api/v1/rankings/classify-topic");
    await page.route("**/api/v1/rankings/classify-topic", async (route) => {
      classifyCalls += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ confidence: 0.91, evidence_terms: ["GLP-1", "糖質", "代謝"], hit_drivers: ["hit_score", "destination_quality"] }) });
    });
    await page.unroute("**/api/v1/rankings/dictionary/suggest");
    await page.route("**/api/v1/rankings/dictionary/suggest", async (route) => {
      dictionaryCalls += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ candidate_terms: [{ topic_label: "glp-1", term: "代謝", confidence: 0.88 }] }) });
    });
    await page.unroute("**/api/v1/rankings/meta-extraction/501/retry");
    await page.route("**/api/v1/rankings/meta-extraction/501/retry", async (route) => {
      retryCalls += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ dispatched: true }) });
    });
    await page.unroute("**/api/v1/lp-analysis/crawl");
    await page.route("**/api/v1/lp-analysis/crawl", async (route) => {
      recrawlCalls += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ started: true }) });
    });

    await page.goto("/?view=pro-database");
    await expect(heading(page)).toBeVisible({ timeout: 15000 });
    await rankingTable(page).getByText("Ad360広告A").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "再分類" }).click();
    await expect(page.getByText("destination_quality")).toBeVisible();
    await page.getByRole("button", { name: "辞書提案" }).click();
    await expect(page.getByText("代謝 (glp-1, 88%)")).toBeVisible();
    await page.getByRole("button", { name: "再クロール" }).click();
    await page.getByRole("button", { name: "再取得" }).nth(0).click();
    await expect.poll(() => classifyCalls).toBe(1);
    await expect.poll(() => dictionaryCalls).toBe(1);
    await expect.poll(() => recrawlCalls).toBe(1);
    await expect.poll(() => retryCalls).toBe(1);
  });

  test("shows snapshot-only and unresolved-lp empty states without breaking the modal", async ({ page }) => {
    await page.unroute("**/api/v1/ads/501");
    await page.route("**/api/v1/ads/501", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 501,
          external_id: "AD-501",
          product_name: "Ad360広告A",
          advertiser_name: "広告主A",
          category: "美容・コスメ",
          cumulative_spend: 120000,
          cumulative_views: 12000,
          published_date: "2026-03-07T00:00:00Z",
          duration_seconds: 15,
          platform: "facebook",
          destination_type: "lead_gen",
          destination_url: "",
          image_url: "",
          video_url: "",
          snapshot_url: "https://example.com/snap.jpg",
          creative_type: "video",
        }),
      });
    });
    await page.unroute("**/api/v1/rankings/ad360/501");
    await page.route("**/api/v1/rankings/ad360/501", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ad_id: 501,
          sections: {
            core: { data: { ad_id: 501, title: "Ad360広告A", advertiser_name: "広告主A", platform: "facebook", genre: "美容・コスメ" }, missing_fields: [] },
            creative: { data: { creative_type: "video", thumbnail_url: "https://example.com/thumb.jpg" }, missing_fields: ["video_url", "image_url"] },
            text: { data: { description: "糖質ケアの動画広告" }, missing_fields: [] },
            analysis: { data: { hit_score: 82, hit_level: "hit" }, missing_fields: [] },
            lp: { data: { status: "unresolved", lp_score: null, url: "" }, missing_fields: ["url", "domain", "lp_score"] },
            quality: { data: { extract_quality_score: 34, needs_media_retry: true, media_status: { viewable: true, downloadable: false, has_lp: false, missing_reasons: ["download_unavailable", "missing_lp"] } }, missing_fields: [] },
          },
        }),
      });
    });

    await page.goto("/?view=pro-database");
    await expect(heading(page)).toBeVisible({ timeout: 15000 });
    await rankingTable(page).getByText("Ad360広告A").first().click();
    await expect(detailModal(page)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("snapshotのみで閲覧可です。DL可能素材は未取得です。")).toBeVisible();
    await expect(page.getByText("LP遷移先が未解決です", { exact: true })).toBeVisible();
    await expect(detailModal(page).getByText("欠損").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "最終LPを見る" })).toBeDisabled();
  });
});
