import {expect, test} from "@playwright/test";

test("dashboard werkt tegen de read-only ontwikkel-API", async ({page}) => {
  await page.goto("/");
  await expect(page.getByText("API: Beschikbaar")).toBeVisible();
  await expect(page.getByRole("heading", {name: "Gemeente Data Platform"})).toBeVisible();
  await expect(page.getByText(/Gemiddelde bevolking voor 2026 ontbreekt/)).toBeVisible();
  await page.getByRole("textbox", {name: "Gemeente", exact: true}).fill("Alp");
  await expect(page.getByRole("button", {name: /Alphen/}).first()).toBeVisible();
  await page.getByRole("button", {name: /Alphen/}).first().click();
  await expect(page.getByRole("heading", {name: /Tijdreeks Alphen/})).toBeVisible();
  await expect(page).toHaveURL(/municipality=/);
  await expect(page.getByRole("heading", {name: /Jaarlijkse verandering Alphen/})).toBeVisible();
});

test("desktop- en mobielweergave zijn leesbaar", async ({browser}) => {
  const desktopContext = await browser.newContext({viewport: {width: 1440, height: 1100}, deviceScaleFactor: 1});
  const desktop = await desktopContext.newPage();
  await desktop.goto("/");
  await expect(desktop.getByText("API: Beschikbaar")).toBeVisible();
  const controls = await Promise.all([desktop.getByLabel("Jaar", {exact: true}).boundingBox(), desktop.getByRole("textbox", {name: "Gemeente", exact: true}).boundingBox(), desktop.getByRole("button", {name: "Wis filters"}).boundingBox()]);
  const bottoms = controls.map((box) => box!.y + box!.height);
  expect(Math.max(...bottoms) - Math.min(...bottoms)).toBeLessThan(2);
  await desktop.getByRole("textbox", {name: "Gemeente", exact: true}).fill("Alp");
  await desktop.getByRole("button", {name: /Alphen/}).first().click();
  await expect(desktop.getByRole("img", {name: /Jaarlijkse verandering Alphen/})).toBeVisible();
  expect(await desktop.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const nationalChart = desktop.getByRole("img", {name: "Nationale bevolkingstrend", exact: true});
  const bounds = await nationalChart.boundingBox();
  for (const label of await nationalChart.locator(".recharts-yAxis .recharts-cartesian-axis-tick-value").all()) {
    const box = await label.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(bounds!.x);
    expect(box!.x + box!.width).toBeLessThanOrEqual(bounds!.x + bounds!.width);
  }
  await desktop.screenshot({path: "../docs/images/dashboard-desktop.png", fullPage: true});
  await desktopContext.close();

  const mobileContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, deviceScaleFactor: 1});
  const mobile = await mobileContext.newPage();
  await mobile.goto("/");
  await expect(mobile.getByText("API: Beschikbaar")).toBeVisible();
  await mobile.getByRole("textbox", {name: "Gemeente", exact: true}).fill("Alp");
  await mobile.getByRole("button", {name: /Alphen/}).first().click();
  await expect(mobile.getByRole("img", {name: /Jaarlijkse verandering Alphen/})).toBeVisible();
  expect(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await mobile.screenshot({path: "../docs/images/dashboard-mobile.png", fullPage: true});
  await mobileContext.close();
});

test("tablet en smalle mobiel behouden structuur en keyboardfilters", async ({page}) => {
  for (const width of [768, 320]) {
    await page.setViewportSize({width, height: 1000});
    await page.goto("/");
    await expect(page.getByText("API: Beschikbaar")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const search = page.getByRole("textbox", {name: "Gemeente", exact: true});
    await search.fill("Alp");
    await expect(page.getByRole("button", {name: /Alphen/}).first()).toBeVisible();
    await search.press("Tab");
    await expect(page.getByRole("button", {name: /Alphen/}).first()).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/municipality=/);
    await page.getByRole("button", {name: "Wis filters"}).click();
    await expect(search).toHaveValue("");
    await expect(page).not.toHaveURL(/municipality=/);
    await expect(page.getByRole("navigation", {name: "Portfolio en documentatie"})).toBeVisible();
  }
});
