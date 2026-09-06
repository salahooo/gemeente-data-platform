import {expect, test} from "@playwright/test";

test("fast startup, controlled cold start, green copy and mobile layout", async ({page, context}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.clock.install();
  let holdReady = false;
  let releaseReady: (() => void) | undefined;
  let dataRequests = 0;
  await page.route("**/ready", async (route) => {
    if (holdReady) await new Promise<void>((resolve) => { releaseReady = resolve; });
    await route.fulfill({json: {status: "ready"}});
  });
  // Frontend-only fixtures keep the smoke independent of API/pipeline availability.
  await page.route("**/api/v1/**", async (route) => {
    dataRequests++;
    const url = new URL(route.request().url());
    const data = url.pathname.endsWith("/years") ? [{year: 2026, has_average_population: false}]
      : url.pathname.includes("/national/") ? [{year: 2026, municipality_count: 342, population_january_1: 18_100_000, average_population: null, missing_average_population_count: 4}]
      : url.pathname.includes("/rankings/") ? [{rank: 1, municipality_code: "GM0363", municipality_name: "Amsterdam", population_january_1: 900_000}]
      : null;
    await route.fulfill({json: data});
  });
  await page.goto("/");
  await expect(page.getByRole("button", {name: "Vernieuwen"})).toBeEnabled();
  await expect(page.getByText("API: Beschikbaar")).toHaveClass(/ok/);
  await expect(page.getByText(/De gratis API wordt/)).toHaveCount(0);
  await expect(page.getByRole("img", {name: /Kaart met inwonertal/})).toBeVisible();
  expect(dataRequests).toBe(4);
  await page.getByRole("button", {name: "Deel weergave"}).click();
  await expect(page.locator(".feedback-success")).toContainText("Weergavelink gekopieerd.");
  await expect(page.getByRole("button", {name: "✓ Link gekopieerd"})).toBeVisible();
  await page.clock.fastForward(3000);
  await expect(page.locator(".feedback-success")).toHaveCount(0);
  holdReady = true; dataRequests = 0;
  await page.reload();
  await expect(page.getByLabel("Dashboard laden")).toBeVisible();
  await expect.poll(() => !!releaseReady).toBe(true);
  await page.clock.fastForward(5001);
  await expect(page.locator(".feedback-warning")).toContainText("De gratis API wordt momenteel opgestart.");
  await expect(page.getByText("API: Opstarten…")).toHaveClass(/starting/);
  await expect(page.getByText("Poging 1 van 7")).toBeVisible();
  expect(dataRequests).toBe(0);
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  releaseReady!();
  await expect(page.getByRole("button", {name: "Vernieuwen"})).toBeEnabled();
  await expect(page.getByText("API: Beschikbaar")).toHaveClass(/ok/);
  await expect(page.getByText(/De gratis API wordt/)).toHaveCount(0);
  expect(dataRequests).toBe(4);
  await page.getByRole("button", {name: "Deel weergave"}).click();
  await expect(page.locator(".feedback-success")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: "test-results/startup-mobile.png", fullPage: true});
  expect(errors).toEqual([]);
});
