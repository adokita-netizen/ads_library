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
};

const proDatabaseHeading = (page: Page) =>
  page.getByRole("heading", { name: "PRO DATABASE", exact: true }).first();
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

const mockPage1: RankingItem[] = [
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
  },
  {
    ad_id: 103,
    rank: 3,
    title: "広告C",
    advertiser_name: "広告主C",
    fine_genre: "美容・コスメ",
    hit_score: 60,
    cumulative_views: 20000,
    estimated_spend_increase_jpy: 180000,
    duration_seconds: 20,
    view_increase: 1400,
    spend_increase: 11000,
    platform: "tiktok",
    is_above_hit_line: true,
  },
];

async function installVisualMocks(page: Page) {
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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: mockPage1,
        total: 120,
        page: 1,
        per_page: 50,
        total_pages: 3,
        fine_genres: ["美容・コスメ", "健康食品"],
        hit_line_threshold: 10000,
      }),
    });
  });

  await page.route("**/api/v1/media/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'><rect width='320' height='180' fill='#e5e7eb'/></svg>",
    });
  });
}

async function prepareStableView(page: Page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
      }
    `,
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installVisualMocks(page);
});

test.describe("Visual Regression @visual", () => {
  test("pro database default view snapshot", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(page.locator('table[aria-label="広告ランキング"]').first()).toBeVisible({ timeout: 10000 });
    await prepareStableView(page);

    const timerLabel = page.getByText(/\((\d+ms|\d+(\.\d+)?s)\)/).first();
    await expect(page).toHaveScreenshot("pro-database-default.png", {
      fullPage: true,
      mask: [timerLabel],
      maxDiffPixels: 2000,
    });
  });

  test("column menu open snapshot", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "カラム" }).click();
    await expect(page.getByRole("button", { name: "デフォルトに戻す" })).toBeVisible();
    await prepareStableView(page);

    const timerLabel = page.getByText(/\((\d+ms|\d+(\.\d+)?s)\)/).first();
    await expect(page).toHaveScreenshot("pro-database-column-menu-open.png", {
      fullPage: true,
      mask: [timerLabel],
      maxDiffPixels: 2000,
    });
  });

  test("score-desc sorted snapshot", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    const scoreHeader = page.locator('table[aria-label="広告ランキング"]').first().getByRole("columnheader", { name: "スコア" });
    await scoreHeader.click();
    await expect(scoreHeader).toHaveAttribute("aria-sort", "descending");
    await prepareStableView(page);

    const timerLabel = page.getByText(/\((\d+ms|\d+(\.\d+)?s)\)/).first();
    await expect(page).toHaveScreenshot("pro-database-score-desc.png", {
      fullPage: true,
      mask: [timerLabel],
      maxDiffPixels: 2500,
    });
  });
});
