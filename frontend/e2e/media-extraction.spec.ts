import { expect, test, type Page } from "@playwright/test";
import { primeAppState } from "./helpers/appState";

const heading = (page: Page) => page.getByRole("heading", { name: "メディア抽出管理" }).first();
const welcomeCloseButton = (page: Page) => page.getByRole("button", { name: "閉じる", exact: true }).first();
const onboardingSkipButton = (page: Page) => page.getByRole("button", { name: "スキップ", exact: true }).first();

async function dismissIntroModalsIfPresent(page: Page) {
  const welcomeClose = welcomeCloseButton(page);
  if (await welcomeClose.isVisible({ timeout: 1500 }).catch(() => false)) {
    await welcomeClose.click({ force: true });
    await expect(welcomeClose).toBeHidden({ timeout: 5000 });
  }

  const skip = onboardingSkipButton(page);
  if (await skip.isVisible({ timeout: 1500 }).catch(() => false)) {
    await skip.click({ force: true });
    await expect(skip).toBeHidden({ timeout: 5000 });
  }
}

async function installMediaExtractionMocks(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "healthy", database: "ok" }),
    });
  });

  await page.route("**/api/v1/rankings/media-extraction-status**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_ads: 12,
        completed: 7,
        pending: 2,
        pending_heavy: 1,
        dispatched: 1,
        failed: 1,
        skipped: 0,
        completion_rate: 58.3,
        status_breakdown: {
          pending: 2,
          pending_heavy: 1,
          dispatched: 1,
          failed: 1,
          completed: 6,
          enriched: 1,
          skipped: 0,
        },
      }),
    });
  });

  await page.route("**/api/v1/rankings/media-extraction-ads**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: 1,
        page: 1,
        per_page: 20,
        ads: [
          {
            id: 321,
            title: "テスト広告",
            advertiser_name: "広告主A",
            creative_type: "video",
            status: "pending",
            platform: "facebook",
            genre: "美容・コスメ",
            topic_label: "GLP-1",
            matched_terms: ["GLP-1", "糖質"],
            has_snapshot: true,
            has_image: false,
            has_video: false,
            has_s3_image: false,
            has_s3_thumbnail: true,
            needs_media_retry: true,
            extract_quality_score: 34,
            updated_at: "2026-03-08T00:40:00Z",
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/rankings/meta-extraction/321", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ad_id: 321,
          dispatched: true,
          message_id: "msg-321",
          strategy: [{ stage: "api", status: "dispatched", message_id: "msg-321" }],
          failure_reason_code: null,
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ad_id: 321,
        creative_urls: {
          thumbnail: "https://example.com/thumb.jpg",
          image: "",
          video: "",
          snapshot: "https://example.com/snapshot.jpg",
        },
        text_fields: {
          title: "テスト広告",
          description: "",
          ocr: [],
          transcript: "",
        },
        extract_source: "snapshot_fallback",
        quality_score: 34,
        missing_fields: ["creative_urls", "text_fields.description", "text_fields.transcript"],
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installMediaExtractionMocks(page);
});

test.describe("Media Extraction Console", () => {
  test("shows extraction status, quality score, missing fields, and evidence URLs", async ({ page }) => {
    await page.goto("/?view=media-management");
    await dismissIntroModalsIfPresent(page);
    await expect(heading(page)).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("heading", { name: "テスト広告" })).toBeVisible();
    await expect(page.getByRole("paragraph").filter({ hasText: "needs_media_retry" })).toBeVisible();
    await expect(page.getByText("quality_score")).toBeVisible();
    await expect(page.getByText("snapshot_fallback")).toBeVisible();
    await expect(page.getByText("text_fields.description")).toBeVisible();
    await expect(page.getByRole("link", { name: "https://example.com/snapshot.jpg" })).toBeVisible();
  });

  test("dispatches ad-level retry and keeps quality console visible", async ({ page }) => {
    await page.goto("/?view=media-management");
    await dismissIntroModalsIfPresent(page);
    await expect(heading(page)).toBeVisible({ timeout: 15000 });

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "この広告を再抽出" }).click();

    await expect(page.getByRole("heading", { name: "テスト広告" })).toBeVisible();
    await expect(page.getByText("missing_fields")).toBeVisible();
    await expect(page.getByText("証拠URL")).toBeVisible();
  });
});
