import {expect, test} from "@playwright/test";

test("dashboard werkt tegen de read-only ontwikkel-API", async ({page}) => {
  await page.goto("/");
  await expect(page.getByText("API: Beschikbaar")).toBeVisible();
  await expect(page.getByRole("heading", {name: "Gemeente Data Platform"})).toBeVisible();
  await expect(page.getByText(/Gemiddelde bevolking voor 2026 ontbreekt/)).toBeVisible();
  await page.getByLabel("Gemeente").fill("Alp");
  await expect(page.getByRole("button", {name: /Alphen/}).first()).toBeVisible();
  await page.getByRole("button", {name: /Alphen/}).first().click();
  await expect(page.getByRole("heading", {name: /Tijdreeks Alphen/})).toBeVisible();
  await expect(page).toHaveURL(/municipality=/);
});

test("desktop- en mobielweergave zijn leesbaar", async ({browser}) => {
  const desktopContext = await browser.newContext({viewport: {width: 1440, height: 1100}, deviceScaleFactor: 1});
  const desktop = await desktopContext.newPage();
  await desktop.goto("/");
  await expect(desktop.getByText("API: Beschikbaar")).toBeVisible();
  await desktop.screenshot({path: "../docs/images/dashboard-desktop.png", fullPage: true});
  await desktopContext.close();

  const mobileContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, deviceScaleFactor: 1});
  const mobile = await mobileContext.newPage();
  await mobile.goto("/");
  await expect(mobile.getByText("API: Beschikbaar")).toBeVisible();
  await mobile.screenshot({path: "../docs/images/dashboard-mobile.png", fullPage: true});
  await mobileContext.close();
});
