import { test, expect, type Page } from "@playwright/test";
import { primeAppState } from "./helpers/appState";

type RankingItem = {
  ad_id: number;
  rank: number;
  title: string;
  advertiser_name: string;
  fine_genre: string;
  hit_score: number;
  cumulative_views: number;
  estimated_spend_increase_jpy: number;
  duration_seconds: number;
  view_increase: number;
  spend_increase: number;
  platform: string;
  is_above_hit_line: boolean;
  language?: string;
};

const proDatabaseHeading = (page: Page) =>
  page.getByRole("heading", { name: "PRO DATABASE", exact: true }).first();

const rankingTable = (page: Page) => page.locator('table[aria-label="広告ランキング"]').first();
const paginationNextButton = (page: Page) =>
  page.locator('button').filter({ hasText: /^次へ$/ }).filter({ hasNotText: "ガイド" }).first();
const onboardingSkipButton = (page: Page) => page.getByRole("button", { name: "スキップ", exact: true }).first();
const welcomeCloseButton = (page: Page) => page.getByRole("button", { name: "閉じる", exact: true }).first();

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

const page1Items: RankingItem[] = [
  {
    ad_id: 101,
    rank: 1,
    title: "広告A",
    advertiser_name: "広告主A",
    fine_genre: "美容・コスメ",
    hit_score: 30,
    cumulative_views: 12000,
    estimated_spend_increase_jpy: 120000,
    duration_seconds: 15,
    view_increase: 800,
    spend_increase: 9000,
    platform: "facebook",
    is_above_hit_line: true,
    language: "ja",
  },
  {
    ad_id: 102,
    rank: 2,
    title: "広告B",
    advertiser_name: "広告主B",
    fine_genre: "健康食品",
    hit_score: 90,
    cumulative_views: 30000,
    estimated_spend_increase_jpy: 220000,
    duration_seconds: 30,
    view_increase: 1800,
    spend_increase: 15000,
    platform: "instagram",
    is_above_hit_line: true,
    language: "ja",
  },
];

const page2Items: RankingItem[] = [
  {
    ad_id: 201,
    rank: 51,
    title: "広告D",
    advertiser_name: "広告主D",
    fine_genre: "教育",
    hit_score: 55,
    cumulative_views: 9000,
    estimated_spend_increase_jpy: 90000,
    duration_seconds: 25,
    view_increase: 600,
    spend_increase: 6000,
    platform: "facebook",
    is_above_hit_line: false,
    language: "ja",
  },
];

async function delay(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function installSlowMocks(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "healthy", database: "ok" }),
    });
  });

  await page.route("**/api/v1/rankings/genre-master**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        genres: [{ genre: "美容・コスメ" }, { genre: "健康食品" }],
      }),
    });
  });

  await page.route("**/api/v1/rankings/search-collections**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ collections: [] }),
    });
  });

  await page.route("**/api/v1/rankings/pro-ranking**", async (route) => {
    const url = new URL(route.request().url());
    const pageNum = Number(url.searchParams.get("page") || "1");

    // Simulate slow network on critical ranking API.
    await delay(pageNum === 1 ? 2800 : 2200);

    const items = pageNum === 2 ? page2Items : page1Items;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items,
        total: 120,
        page: pageNum,
        per_page: 50,
        total_pages: 3,
        fine_genres: ["美容・コスメ", "健康食品"],
        hit_line_threshold: 10000,
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installSlowMocks(page);
});

test.describe("Slow Network Regression @slow", () => {
  test("shows loading skeleton during delayed first fetch and then renders table", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });

    // Table with aria-label is not rendered while the delayed request is pending.
    await expect(rankingTable(page)).toHaveCount(0);
    await expect(page.getByPlaceholder("タイトル・広告主で絞り込み...")).toHaveCount(0);

    await expect(rankingTable(page)).toBeVisible({ timeout: 12000 });
    await expect(page.getByPlaceholder("タイトル・広告主で絞り込み...")).toBeVisible();
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告A");
  });

  test("keeps UI responsive with loading overlay during delayed pagination", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(rankingTable(page)).toBeVisible({ timeout: 12000 });
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告A");

    await paginationNextButton(page).click();

    const overlaySpinner = page.locator("div.absolute.inset-0 svg.animate-spin");
    await expect(overlaySpinner).toBeVisible({ timeout: 3000 });
    await expect(page.getByText("2 / 3 ページ")).toBeVisible({ timeout: 12000 });
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告D");
  });
});
