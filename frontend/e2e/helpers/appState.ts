import type { Page } from "@playwright/test";

interface PrimeAppStateOptions {
  demoMode?: boolean;
  disableWindowOpen?: boolean;
}

const FALLBACK_IMAGE_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="#e5e7eb"/></svg>';

export async function primeAppState(
  page: Page,
  options: PrimeAppStateOptions = {},
) {
  const { demoMode = false, disableWindowOpen = false } = options;
  await page.addInitScript(
    ({ demoModeEnabled, disableWindowOpenEnabled }) => {
      window.localStorage.setItem("onboarding_completed", "true");
      window.localStorage.setItem("vaap-onboarded", "true");
      window.localStorage.setItem("vaap_onboarding_completed", "true");
      if (demoModeEnabled) {
        window.localStorage.setItem("vaap-demo-mode", "true");
      } else {
        window.localStorage.removeItem("vaap-demo-mode");
      }
      if (disableWindowOpenEnabled) {
        window.open = () => null;
      }
    },
    {
      demoModeEnabled: demoMode,
      disableWindowOpenEnabled: disableWindowOpen,
    },
  );

  // Silence shared background requests that are not relevant to most E2E cases.
  // More specific route handlers defined in individual specs still take precedence.
  await page.route("**/api/v1/rankings/products**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [],
        total: 0,
      }),
    });
  });

  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "healthy",
        database: "ok",
      }),
    });
  });

  await page.route("**/api/v1/media/thumbnail/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: FALLBACK_IMAGE_SVG,
    });
  });

  await page.route("**/api/v1/media/image/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: FALLBACK_IMAGE_SVG,
    });
  });
}
