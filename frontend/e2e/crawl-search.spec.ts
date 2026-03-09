import { test, expect, type Page } from "@playwright/test";
import { primeAppState } from "./helpers/appState";

async function installBaseMocks(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "healthy", database: "ok" }),
    });
  });

  await page.route("**/api/v1/rankings/products**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            ad_id: 1,
            rank: 1,
            platform: "facebook",
            management_id: "AD-1",
            product_name: "テスト商材",
            genre: "beauty",
            cumulative_views: 1000,
            cumulative_spend: 10000,
          },
        ],
        total: 1,
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installBaseMocks(page);
});

test.describe("Crawl Search Input @table", () => {
  test("submits with Enter and normalizes full-width spaces", async ({ page }) => {
    let receivedQuery = "";

    await page.route("**/api/v1/rankings/quick-crawl", async (route) => {
      const body = route.request().postDataJSON() as { query?: string; limit?: number };
      receivedQuery = body.query || "";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "completed", ads_found: 3 }),
      });
    });

    await page.goto("/?view=search");
    await page.getByRole("button", { name: "検索" }).first().click();
    await page.getByRole("button", { name: "広告クロール" }).first().click();
    await expect(page.getByRole("heading", { name: "広告クロール" })).toBeVisible();

    const input = page.getByPlaceholder("商材名、競合名、カテゴリなど");
    await input.fill("　テスト商材　");
    await input.press("Enter");

    await expect(page.getByRole("heading", { name: "広告クロール" })).toBeHidden({ timeout: 10000 });
    await expect.poll(() => receivedQuery).toBe("テスト商材");
    await expect(page.getByText("クロール反映:")).toBeVisible();
    await expect(page.getByText("追加 3件")).toBeVisible();
  });

  test("shows validation for blank full-width spaces", async ({ page }) => {
    await page.goto("/?view=search");
    await page.getByRole("button", { name: "検索" }).first().click();
    await page.getByRole("button", { name: "広告クロール" }).first().click();

    const input = page.getByPlaceholder("商材名、競合名、カテゴリなど");
    await input.fill("　　　");
    await input.press("Enter");

    await expect(page.getByText("検索キーワードを入力してください")).toBeVisible();
  });

  test("shows server failure message from quick-crawl", async ({ page }) => {
    await page.route("**/api/v1/rankings/quick-crawl", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "failed", message: "クロールに失敗しました" }),
      });
    });

    await page.goto("/?view=search");
    await page.getByRole("button", { name: "検索" }).first().click();
    await page.getByRole("button", { name: "広告クロール" }).first().click();
    await page.getByPlaceholder("商材名、競合名、カテゴリなど").fill("GLP-1");
    await page.getByRole("button", { name: "クロール開始" }).click();

    await expect(page.getByText("クロールに失敗しました")).toBeVisible();
  });

  test("shows timeout detail when quick-crawl returns timeout error", async ({ page }) => {
    await page.route("**/api/v1/rankings/quick-crawl", async (route) => {
      await route.fulfill({
        status: 504,
        contentType: "application/json",
        body: JSON.stringify({ detail: "タイムアウトが発生しました" }),
      });
    });

    await page.goto("/?view=search");
    await page.getByRole("button", { name: "検索" }).first().click();
    await page.getByRole("button", { name: "広告クロール" }).first().click();
    await page.getByPlaceholder("商材名、競合名、カテゴリなど").fill("GLP-1");
    await page.getByRole("button", { name: "クロール開始" }).click();

    await expect(page.getByText(/タイムアウト|timeout|HTTP 504|クロールの開始に失敗/i)).toBeVisible();
  });

  test("thumbnail resolves to fallback proxy or direct URL", async ({ page }) => {
    await page.route("**/api/v1/rankings/products**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              ad_id: 1,
              rank: 1,
              platform: "facebook",
              management_id: "AD-1",
              product_name: "低解像度テスト",
              genre: "beauty",
              thumbnail_url: "https://cdn.example.com/s100x100/thumb.jpg",
              image_url: "https://cdn.example.com/s100x100/image.jpg",
              cumulative_views: 1000,
              cumulative_spend: 10000,
            },
          ],
          total: 1,
        }),
      });
    });
    await page.route("**/api/v1/media/thumbnail/1", async (route) => route.abort());
    await page.route("**/api/v1/media/image/1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "image/jpeg",
        body: Buffer.from([255, 216, 255, 217]),
      });
    });

    await page.goto("/?view=search");
    await page.getByRole("button", { name: "検索" }).first().click();
    const thumb = page.locator("table tbody tr").first().locator("td").nth(1).locator("img");
    await expect(thumb).toBeVisible();
    const src = (await thumb.getAttribute("src")) || "";
    expect(src).toMatch(/\/api\/v1\/media\/image\/1|thumb\.jpg|image\.jpg/);
  });
});
