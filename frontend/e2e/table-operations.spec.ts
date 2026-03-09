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
const blockingOverlay = (page: Page) => page.locator("div.fixed.inset-0.z-\\[70\\]").first();
const paginationPageButton = (page: Page, pageNumber: number) =>
  page.getByRole("button", { name: String(pageNumber), exact: true }).last();

async function dismissBlockingOverlay(page: Page) {
  const overlay = blockingOverlay(page);
  if (!(await overlay.isVisible({ timeout: 1000 }).catch(() => false))) return;

  const closeButton = overlay.locator("button.w-8.h-8, button[aria-label='閉じる']").first();
  if (await closeButton.isVisible().catch(() => false)) {
    await closeButton.click();
  } else {
    await page.keyboard.press("Escape");
  }
  await expect(overlay).toBeHidden({ timeout: 5000 });
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
    language: "ja",
  },
];

const mockPage2: RankingItem[] = [
  {
    ad_id: 201,
    rank: 51,
    title: "広告D",
    advertiser_name: "広告主D",
    fine_genre: "美容・コスメ",
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

const mockPage3: RankingItem[] = [
  {
    ad_id: 301,
    rank: 101,
    title: "広告E",
    advertiser_name: "広告主E",
    fine_genre: "健康食品",
    hit_score: 45,
    cumulative_views: 7000,
    estimated_spend_increase_jpy: 70000,
    duration_seconds: 10,
    view_increase: 400,
    spend_increase: 4000,
    platform: "instagram",
    is_above_hit_line: false,
    language: "ja",
  },
];

async function installProRankingMocks(page: Page) {
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
    if (route.request().method() !== "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ collections: [] }),
    });
  });

  await page.route("**/api/v1/rankings/pro-ranking**", async (route) => {
    const url = new URL(route.request().url());
    const pageNum = Number(url.searchParams.get("page") || "1");
    const perPage = Number(url.searchParams.get("page_size") || url.searchParams.get("per_page") || "50");
    const allItems = [...mockPage1, ...mockPage2, ...mockPage3];
    const fallbackPageItems = allItems.slice((pageNum - 1) * perPage, pageNum * perPage);
    const pageItems = pageNum === 1 ? mockPage1 : pageNum === 2 ? mockPage2 : pageNum === 3 ? mockPage3 : fallbackPageItems;

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: pageItems,
        total: 120,
        page: pageNum,
        per_page: perPage,
        total_pages: Math.ceil(120 / perPage),
        fine_genres: ["美容・コスメ", "健康食品"],
        hit_line_threshold: 10000,
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installProRankingMocks(page);
});

test.describe("Table Operations Extended @table", () => {
  test("column toggle can hide and restore advertiser column", async ({ page }) => {
    await page.goto("/");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await dismissBlockingOverlay(page);
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });

    const advertiserHeader = rankingTable(page).getByRole("columnheader", { name: "広告主" });
    await expect(advertiserHeader).toBeVisible();

    await page.getByRole("main").getByRole("button", { name: "カラム" }).click();
    await page.getByRole("checkbox", { name: "広告主" }).click();
    await expect(advertiserHeader).toBeHidden();

    await page.getByRole("button", { name: "デフォルトに戻す" }).click();
    await expect(advertiserHeader).toBeVisible();
  });

  test("score sort toggles order and aria-sort state", async ({ page }) => {
    await page.goto("/");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await dismissBlockingOverlay(page);
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });

    const scoreHeader = rankingTable(page).getByRole("columnheader", { name: "スコア" });
    await expect(scoreHeader).toHaveAttribute("aria-sort", "none");

    await scoreHeader.click();
    await expect(scoreHeader).toHaveAttribute("aria-sort", "descending");
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告B");

    await scoreHeader.click();
    await expect(scoreHeader).toHaveAttribute("aria-sort", "ascending");
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告A");
  });

  test("pagination moves to next page and updates table rows", async ({ page }) => {
    await page.goto("/");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await dismissBlockingOverlay(page);
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });

    await expect(page.getByText("1 / 3 ページ")).toBeVisible();
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告A");

    await paginationPageButton(page, 2).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("広告D");
  });
});
