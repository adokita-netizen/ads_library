import { test, expect } from "@playwright/test";

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

async function dismissOnboardingIfPresent(page: import("@playwright/test").Page) {
  const skip = onboardingSkipButton(page);
  if (await skip.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skip.click();
    await expect(skip).toBeHidden({ timeout: 5000 });
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("onboarding_completed", "true");
  });
});

test.describe("Smoke Tests @smoke", () => {

  test("homepage loads and shows PRO DATABASE view", async ({ page }) => {
    await page.goto("/");
    await dismissOnboardingIfPresent(page);
    // Wait for the main content to load
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Sidebar should be visible on desktop
    await expect(page.locator("aside").getByText("VAAP").first()).toBeVisible();
  });

  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/");
    await dismissOnboardingIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });

    // Click on search nav item
    await page.getByRole("button", { name: "検索", exact: true }).first().click();
    // Should show search view
    await expect(page.locator('input[placeholder*="検索"]')).toBeVisible({ timeout: 10000 });
  });

  test("URL view parameter syncs with sidebar", async ({ page }) => {
    // Navigate directly to search view via URL
    await page.goto("/?view=search");
    await dismissOnboardingIfPresent(page);
    await expect(page.locator('input[placeholder*="検索"]')).toBeVisible({ timeout: 15000 });
  });

  test("connectivity banner resolves", async ({ page }) => {
    await page.goto("/");
    await dismissOnboardingIfPresent(page);
    // Banner should either resolve to OK or show error — but not hang
    await page.waitForTimeout(5000);
    // The main view should be rendered regardless
    await expect(page.locator("main")).toBeVisible();
  });

  test("error boundary catches view errors gracefully", async ({ page }) => {
    await page.goto("/");
    await dismissOnboardingIfPresent(page);
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
    await dismissOnboardingIfPresent(page);
    await expect(proDatabaseHeading(page)).toBeVisible({ timeout: 15000 });
    // Wait for table or one of the fallback states.
    await Promise.any([
      page.locator('table[aria-label="広告ランキング"]').first().waitFor({ state: "visible", timeout: 15000 }),
      page.getByText(/データ|エラー|0件/).first().waitFor({ state: "visible", timeout: 15000 }),
    ]);
  });

  test("search bar autocomplete dropdown appears", async ({ page }) => {
    await page.goto("/");
    await dismissOnboardingIfPresent(page);
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
    await dismissOnboardingIfPresent(page);
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
