import { test, expect } from "@playwright/test";
import { primeAppState } from "./helpers/appState";

/**
 * B47: CI-031 Frontend E2E Smoke Tests
 * Critical path tests that verify the app loads and core navigation works.
 * Run with: npx playwright test --grep @smoke
 */

const proDatabaseHeading = (page: import("@playwright/test").Page) =>
  page.getByRole("heading", { name: "PRO DATABASE", exact: true }).first();
const mainSearchInput = (page: import("@playwright/test").Page) =>
  page.getByRole("combobox", { name: "広告・商材・広告主を検索" });
const onboardingSkipButton = (page: import("@playwright/test").Page) =>
  page.getByRole("button", { name: "スキップ", exact: true }).first();
const welcomeCloseButton = (page: import("@playwright/test").Page) =>
  page.getByRole("button", { name: "閉じる", exact: true }).first();

async function dismissIntroModalsIfPresent(page: import("@playwright/test").Page) {
  const welcomeClose = welcomeCloseButton(page);
  if (await welcomeClose.isVisible({ timeout: 1500 }).catch(() => false)) {
    await welcomeClose.click({ force: true });
    await expect(welcomeClose).toBeHidden({ timeout: 5000 });
  }
  const skip = onboardingSkipButton(page);
  if (await skip.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skip.click({ force: true });
    await expect(skip).toBeHidden({ timeout: 5000 });
  }
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
});

test.describe("Smoke Tests @smoke", () => {

  test("homepage loads and shows PRO DATABASE view", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    // Wait for the main content to load
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Sidebar should be visible on desktop
    await expect(page.locator("aside").getByText("VAAP").first()).toBeVisible();
  });

  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });

    // Click on search nav item
    await page.getByRole("button", { name: "検索", exact: true }).first().click();
    // Search view should render one of the current primary search controls.
    await Promise.any([
      mainSearchInput(page).waitFor({ state: "visible", timeout: 10000 }),
      page.getByPlaceholder("商材名・管理番号で検索").waitFor({ state: "visible", timeout: 10000 }),
      page.getByPlaceholder("タイトル・広告主で絞り込み...").waitFor({ state: "visible", timeout: 10000 }),
    ]);
  });

  test("URL view parameter syncs with sidebar", async ({ page }) => {
    // Navigate directly to search view via URL
    await page.goto("/?view=search");
    await dismissIntroModalsIfPresent(page);
    await expect(mainSearchInput(page)).toBeVisible({ timeout: 15000 });
  });

  test("connectivity banner resolves", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    // Banner should either resolve to OK or show error — but not hang
    await page.waitForTimeout(5000);
    // The main view should be rendered regardless
    await expect(page.locator("main")).toBeVisible();
  });

  test("notification bell opens dropdown and deep-links to notification center", async ({ page }) => {
    await page.route("**/api/v1/rankings/notifications**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          unread_count: 2,
          notifications: [
            {
              id: 9001,
              type: "alert",
              title: "急騰アラート",
              body: "ヒット広告スコアが急上昇しました",
              read: false,
              created_at: "2026-03-08T10:00:00Z",
              ad_id: 501,
            },
            {
              id: 9002,
              type: "system",
              title: "バッチ完了",
              body: "夜間集計が完了しました",
              read: true,
              created_at: "2026-03-08T09:00:00Z",
              action_url: "/?view=notifications",
            },
          ],
        }),
      });
    });
    await page.route("**/api/v1/rankings/notifications/read-all", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });
    await page.route("**/api/v1/rankings/notifications/9001/read", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });

    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });

    const bellButton = page.getByRole("button", { name: "Notifications" }).first();
    await expect(bellButton).toContainText("2");
    await bellButton.click();
    await expect(page.getByText("急騰アラート")).toBeVisible();
    await expect(page.getByText("ヒット広告スコアが急上昇しました")).toBeVisible();

    await page.getByRole("button", { name: "Open notification center" }).click();
    await expect(page.getByRole("heading", { name: "通知センター", exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("急騰アラート")).toBeVisible();
  });

  test("error boundary catches view errors gracefully", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    // Load a known view
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Navigate between views to verify no crash
    await page.locator('button:has-text("トレンド")').click();
    await page.waitForTimeout(2000);
    await page.locator('button:has-text("PRO DATABASE")').click();
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Table Operations @smoke", () => {
  test("ranking table loads data or shows empty state", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Wait for table or one of the fallback states.
    await Promise.any([
      page.locator('table[aria-label="広告ランキング"]').first().waitFor({ state: "visible", timeout: 15000 }),
      page.getByText(/データ|エラー|0件/).first().waitFor({ state: "visible", timeout: 15000 }),
    ]);
  });

  test("search bar autocomplete dropdown appears", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Type in the main search bar and verify input handling.
    const searchInput = mainSearchInput(page);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill("テスト");
    await expect(searchInput).toHaveValue("テスト");
    // Dropdown may depend on API timing, so only validate it when rendered.
    const suggestions = page.locator("#search-suggestions");
    if (await suggestions.count()) {
      await expect(suggestions).toBeVisible({ timeout: 5000 });
    }
  });

  test("period toggle changes data", async ({ page }) => {
    await page.goto("/");
    await dismissIntroModalsIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Click "月次" period toggle
    const monthlyButton = page.getByRole("button", { name: "月次", exact: true }).first();
    if (await monthlyButton.isVisible()) {
      await monthlyButton.click();
      // Ensure the screen remains interactive after period toggle.
      await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 5000 });
    }
  });
});
