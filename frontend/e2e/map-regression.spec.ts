import {expect, test} from "@playwright/test";

test("map selection and shared URL survive refresh without browser errors", async ({page}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  // Local lineage metadata is unavailable (503); keep this frontend smoke independent
  // of pipeline state. Geometry and all population/selection requests remain real.
  await page.route("**/api/v1/lineage/latest", (route) => route.fulfill({json: null}));
  await page.goto("/");
  await expect(page.getByText("API: Beschikbaar")).toBeVisible();
  const map = page.getByRole("img", {name: /Kaart met inwonertal per gemeente/});
  await expect(map).toBeVisible();
  const amsterdam = map.getByRole("button", {name: /^Amsterdam \(GM0363\)/}).first();
  await expect(amsterdam).toHaveAttribute("d", /^M.+Z$/);
  await expect(amsterdam).not.toHaveAttribute("aria-label", /waarde onbekend/);
  await amsterdam.focus();
  await amsterdam.press("Enter");
  await expect(page).toHaveURL(/municipality=GM0363/);
  await expect(amsterdam).toHaveClass("map-selected");
  await page.getByRole("textbox", {name: "Vergelijk met gemeente", exact: true}).fill("Alp");
  await page.getByRole("button", {name: /Alphen/}).filter({hasNot: page.locator("title")}).first().click();
  await expect(page).toHaveURL(/compare=GM/);
  const sharedUrl = page.url();
  const selectedYear = await page.getByLabel("Jaar", {exact: true}).inputValue();
  await page.reload();
  await expect(page.getByText("API: Beschikbaar")).toBeVisible();
  await expect(page.getByRole("heading", {name: "Tijdreeks Amsterdam", exact: true})).toBeVisible();
  await expect(page.getByRole("region", {name: "Bevolkingsanalyses"}).getByRole("img", {name: "Vergelijking geselecteerde gemeenten", exact: true})).toBeVisible();
  await expect(amsterdam).toHaveClass("map-selected");
  await expect(page.getByLabel("Jaar", {exact: true})).toHaveValue(selectedYear);
  await expect(page).toHaveURL(sharedUrl);
  expect(errors).toEqual([]);
});
