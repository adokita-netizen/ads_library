import { test, expect, type Page } from "@playwright/test";
import { checkA11y, injectAxe } from "axe-playwright";
import { designTokens, platformBadgeColors } from "../src/lib/constants";
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

const mockItems: RankingItem[] = [
  {
    ad_id: 9001,
    rank: 1,
    title: "コントラスト検証A",
    advertiser_name: "広告主A",
    fine_genre: "美容・コスメ",
    hit_score: 88,
    cumulative_views: 32000,
    estimated_spend_increase_jpy: 280000,
    duration_seconds: 20,
    view_increase: 1900,
    spend_increase: 20000,
    platform: "facebook",
    is_above_hit_line: true,
  },
];

async function installMocks(page: Page) {
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
      body: JSON.stringify({ genres: [{ genre: "美容・コスメ" }] }),
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
        items: mockItems,
        total: mockItems.length,
        page: 1,
        per_page: 50,
        total_pages: 1,
        fine_genres: ["美容・コスメ"],
        hit_line_threshold: 10000,
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeAppState(page);
  await installMocks(page);
});

test.describe("Color Token Contrast Automation @a11y-contrast", () => {
  test("design token foreground/background pairs satisfy contrast rule", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "PRO DATABASE", exact: true }).first()).toBeVisible({ timeout: 15000 });

    const hitPairs = Object.entries(designTokens.hit).map(([name, token]) => ({
      label: `hit-${name}`,
      className: `${token.bg} ${token.text}`,
    }));
    const statusPairs = Object.entries(designTokens.status).map(([name, token]) => ({
      label: `status-${name}`,
      className: `${token.bg} ${token.text}`,
    }));
    const platformPairs = Object.entries(platformBadgeColors).map(([name, className]) => ({
      label: `platform-${name}`,
      className,
    }));

    const pairs = [...hitPairs, ...statusPairs, ...platformPairs];

    await page.evaluate((items) => {
      const existing = document.getElementById("token-contrast-sandbox");
      if (existing) {
        existing.remove();
      }

      const sandbox = document.createElement("section");
      sandbox.id = "token-contrast-sandbox";
      sandbox.setAttribute("aria-label", "token contrast sandbox");
      sandbox.className = "m-4 p-4 bg-white border border-gray-200 rounded-lg flex flex-wrap gap-3";

      for (const item of items) {
        const node = document.createElement("span");
        node.className = `${item.className} text-sm px-3 py-1 rounded border border-black/5`;
        node.textContent = item.label;
        sandbox.appendChild(node);
      }

      document.body.appendChild(sandbox);
    }, pairs);

    await injectAxe(page);
    await checkA11y(
      page,
      "#token-contrast-sandbox",
      {
        axeOptions: {
          runOnly: {
            type: "rule",
            values: ["color-contrast"],
          },
        },
        includedImpacts: ["serious", "critical"],
        detailedReport: true,
      },
      false,
    );
  });
});
