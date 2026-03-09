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
const productDetailModal = (page: Page) => page.locator("div.fixed.inset-0.z-50").first();
const paginationPageButton = (page: Page, pageNumber: number) =>
  page.getByRole("button", { name: String(pageNumber), exact: true }).last();
const settingsButton = (page: Page) => page.getByRole("button", { name: "設定", exact: true });
const settingsBackButton = (page: Page) => page.getByRole("button", { name: /戻る/ }).first();

const page1Items: RankingItem[] = [
  {
    ad_id: 101,
    rank: 1,
    title: "美容広告A",
    advertiser_name: "広告主A",
    fine_genre: "美容・コスメ",
    hit_score: 78,
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
    title: "健康広告B",
    advertiser_name: "広告主B",
    fine_genre: "健康食品",
    hit_score: 66,
    cumulative_views: 9800,
    estimated_spend_increase_jpy: 98000,
    duration_seconds: 30,
    view_increase: 500,
    spend_increase: 8000,
    platform: "instagram",
    is_above_hit_line: false,
    language: "ja",
  },
];

const page2Items: RankingItem[] = [
  {
    ad_id: 201,
    rank: 51,
    title: "美容広告D",
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

async function installStateSyncMocks(page: Page) {
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
    const genre = url.searchParams.get("genre");

    let items = pageNum === 2 ? page2Items : page1Items;
    if (genre) {
      items = items.filter((item) => item.fine_genre === genre);
    }

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

  await page.route("**/api/v1/ads/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/analysis")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
      return;
    }

    const id = Number(url.split("/ads/")[1]?.split("?")[0] || "0");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id,
        title: `詳細広告${id}`,
        advertiser_name: `広告主${id}`,
        genre: id >= 200 ? "美容・コスメ" : "健康食品",
        image_url: null,
        video_url: null,
        snapshot_url: null,
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installStateSyncMocks(page);
});

test.describe("List/Detail State Sync Regression @state", () => {
  test("filter URL params stay unchanged after opening and closing detail modal", async ({ page }) => {
    await page.goto("/?view=pro-database&genre=%E7%BE%8E%E5%AE%B9%E3%83%BB%E3%82%B3%E3%82%B9%E3%83%A1&period=14d&sort=hit_score");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("美容広告A");

    await rankingTable(page).getByText("美容広告A").first().click();
    await expect(productDetailModal(page)).toBeVisible({ timeout: 10000 });

    await productDetailModal(page).locator("button.w-8.h-8").first().click();
    await expect(productDetailModal(page)).toHaveCount(0);
    await expect(rankingTable(page)).toBeVisible();

    await expect(page).toHaveURL(/view=pro-database/);
    await expect(page).toHaveURL(/genre=%E7%BE%8E%E5%AE%B9%E3%83%BB%E3%82%B3%E3%82%B9%E3%83%A1/);
    await expect(page).toHaveURL(/period=14d/);
    await expect(page).toHaveURL(/sort=hit_score/);
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("美容広告A");
  });

  test("current pagination stays on same page after detail modal close", async ({ page }) => {
    await page.goto("/?view=pro-database");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("1 / 3 ページ")).toBeVisible();

    await paginationPageButton(page, 2).click();
    await expect(page).toHaveURL(/page=2/, { timeout: 10000 });
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("美容広告D");

    await rankingTable(page).getByText("美容広告D").first().click();
    await expect(productDetailModal(page)).toBeVisible({ timeout: 10000 });

    await productDetailModal(page).locator("button.w-8.h-8").first().click();
    await expect(productDetailModal(page)).toHaveCount(0);
    await expect(page).toHaveURL(/view=pro-database/);
    await expect(page).toHaveURL(/page=2/);
    await expect(rankingTable(page).locator("tbody tr").first()).toContainText("美容広告D");
  });

  test("settings keeps its view param even if another URL update drops it", async ({ page }) => {
    await page.goto("/?view=settings");
    await expect(page).toHaveURL(/view=settings/);
    await expect(settingsBackButton(page)).toBeVisible({ timeout: 10000 });

    await page.evaluate(() => {
      const params = new URLSearchParams(window.location.search);
      params.delete("view");
      const qs = params.toString();
      window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
      window.dispatchEvent(new Event("vaap:url-state-change"));
    });

    await expect(page).toHaveURL(/view=settings/);
    await expect(settingsBackButton(page)).toBeVisible();
  });

  test("settings back button returns to pro database and restores the view param", async ({ page }) => {
    await page.goto("/?view=pro-database&period=14d");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });

    await settingsButton(page).click();
    await expect(page).toHaveURL(/view=settings/);
    await expect(settingsBackButton(page)).toBeVisible({ timeout: 10000 });

    await settingsBackButton(page).click();
    await expect(page).toHaveURL(/view=pro-database/);
    await expect(page).toHaveURL(/period=14d/);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
  });

  test("keeps URL filter state after reload", async ({ page }) => {
    await page.goto("/?view=pro-database&period=14d&sort=hit_score&platform=facebook");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(rankingTable(page)).toBeVisible({ timeout: 10000 });

    await page.reload();

    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/view=pro-database/);
    await expect(page).toHaveURL(/period=14d/);
    await expect(page).toHaveURL(/sort=hit_score/);
    await expect(page).toHaveURL(/platform=facebook/);
  });

  test("retry action dispatches low-quality media and refreshes table summary", async ({ page }) => {
    let proRankingCalls = 0;
    let retryCalls = 0;

    await page.unroute("**/api/v1/rankings/pro-ranking**");
    await page.route("**/api/v1/rankings/pro-ranking**", async (route) => {
      proRankingCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: page1Items,
          total: 2,
          page: 1,
          per_page: 50,
          total_pages: 1,
          fine_genres: ["美容・コスメ", "健康食品"],
          hit_line_threshold: 10000,
        }),
      });
    });
    await page.route("**/api/v1/rankings/batch-extract-media**", async (route) => {
      retryCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ dispatched: 2, errors: 0, retry_candidates_dispatched: 1 }),
      });
    });

    await page.goto("/?view=pro-database");
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    await expect
      .poll(() => proRankingCalls, { timeout: 10000 })
      .toBeGreaterThan(0);
    const before = proRankingCalls;

    await page.getByRole("button", { name: "低品質を再抽出" }).click();

    await expect.poll(() => retryCalls).toBe(1);
    await expect(page.getByText("再抽出投入: 2件", { exact: false })).toBeVisible();
    await expect
      .poll(() => proRankingCalls, { timeout: 10000 })
      .toBeGreaterThan(before);
  });
});
