import { expect, test } from "@playwright/test";

/**
 * Primary user journey: land -> search with location autocomplete -> filter & sort ->
 * open a journey -> register -> save it -> see it on the dashboard -> remove it -> sign out.
 */
test("search, inspect, save and manage a journey", async ({ page }) => {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("One Destination");
  await expect(page.getByRole("note").filter({ hasText: "Demonstration data" })).toBeVisible();

  // Location autocomplete accepts local spellings.
  const from = page.getByRole("combobox", { name: "From" });
  await from.fill("Toshk");
  await page.getByRole("option", { name: /Tashkent/ }).click();
  const to = page.getByRole("combobox", { name: "To" });
  await to.fill("Buxoro");
  await page.getByRole("option", { name: /Bukhara/ }).click();
  await page.getByRole("button", { name: "Search journeys" }).click();

  await expect(page).toHaveURL(/\/search\?origin=tashkent&destination=bukhara/);
  await expect(page.getByRole("heading", { name: /Tashkent.*Bukhara/ })).toBeVisible();
  const results = page.getByRole("list", { name: "Journeys" }).getByRole("listitem");
  await expect(results.first()).toBeVisible();
  await expect(page.getByText("Sources & data freshness")).toBeVisible();

  // Sorting by price produces non-decreasing prices.
  await page.getByLabel("Sort by").selectOption("price");
  await expect(page).toHaveURL(/sort=price/);
  await expect(page.getByText("Updating results…")).toHaveCount(0);
  const prices = await results.locator("p.text-gold").allInnerTexts();
  const numbers = prices.map((p) => Number(p.replace(/[^\d–].*$/, "").replace(/\D/g, "")));
  expect(numbers).toEqual([...numbers].sort((a, b) => a - b));

  // Mode filter: hide taxis.
  await page.getByRole("button", { name: "Taxi", pressed: true }).click();
  await expect(page).toHaveURL(/modes=/);
  await expect(page.getByRole("button", { name: "Taxi", pressed: false })).toBeVisible();

  // Journey detail.
  await results.first().getByRole("link", { name: /View details/ }).click();
  await expect(page).toHaveURL(/\/journeys\//);
  await expect(page.getByText("Booking not available.")).toBeVisible();
  await expect(page.getByRole("table").first()).toBeVisible();
  const journeyUrl = page.url();

  // Saving requires an account: sign-in link returns to the journey after registering.
  await page.getByRole("link", { name: "Sign in to save" }).click();
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct horse battery 9");
  await page.getByRole("button", { name: "Create account" }).click();
  // ?next= is preserved through sign-in -> register, so we land back on the journey.
  await expect(page).toHaveURL(journeyUrl);
  await page.getByRole("button", { name: "Save journey" }).click();
  await expect(page.getByRole("link", { name: /Saved/ })).toBeVisible();

  await page.getByRole("link", { name: /Saved · View dashboard/ }).click();
  await expect(page.getByRole("heading", { name: /Saved journeys/ })).toContainText("(1)");
  await expect(page.getByRole("listitem").getByText("Tashkent → Bukhara")).toBeVisible();

  // Remove with confirmation.
  await page.getByRole("button", { name: /Remove saved journey/ }).click();
  await page.getByRole("button", { name: "Confirm remove" }).click();
  await expect(page.getByText("No saved journeys yet")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Sign in" })).toBeVisible();
});

test("assistant turns a sentence into real search results", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /describe your trip/i }).click();
  await page.getByLabel("Describe your trip").fill("Cheapest way from Tashkent to Samarkand tomorrow");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/I found \d+ option/)).toBeVisible();
  await expect(page.getByText(/demonstration data/).first()).toBeVisible();
  await page.getByRole("link", { name: /See all .* results/ }).click();
  await expect(page).toHaveURL(/origin=tashkent&destination=samarkand.*sort=price/);
});

test("invalid searches show clear errors", async ({ page }) => {
  await page.goto("/search?origin=tashkent&destination=tashkent&date=2026-12-01");
  const alert = page.locator("main [role=alert]");
  await expect(alert).toContainText("Origin and destination must be different");
  await page.goto("/search?origin=atlantis&destination=tashkent&date=2026-12-01");
  await expect(alert).toContainText("recognise");
});
