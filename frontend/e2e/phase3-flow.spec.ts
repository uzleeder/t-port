import { expect, test } from "@playwright/test";

/**
 * Phase 3 full flow: search -> compare -> details -> save -> reopen from the dashboard ->
 * booking hand-off -> operator page.
 *
 * Needs the API's fictional TEST provider (TPORT_ENABLE_SYNTHETIC_BOOKING=true, dev/test only). Its
 * booking host is on the reserved .test domain, so the operator page is a Playwright test double:
 * nothing leaves the machine.
 */
test("search, compare, save, reopen and hand off to the operator", async ({ page }) => {
  test.setTimeout(150_000); // seven pages; the dev server compiles each on first visit
  const email = `e2e-p3-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  // Playwright cannot intercept the target of a navigation redirect, so the hand-off request itself is
  // intercepted: it still goes to the real API (which counts it), the 303 is checked, and the operator
  // page is a test double served in its place.
  let operatorUrl = "";
  await page.route("**/api/v1/journeys/*/book", async (route) => {
    const response = await route.fetch({ maxRedirects: 0 });
    expect(response.status()).toBe(303);
    expect(response.headers()["referrer-policy"]).toBe("no-referrer");
    operatorUrl = response.headers()["location"] ?? "";
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><title>Operator</title><h1>Operator booking page (test double)</h1>",
    });
  });

  // Search a route served by the demo dataset and the TEST provider.
  await page.goto("/search?origin=tashkent&destination=namangan&date=tomorrow&max_transfers=0");
  await expect(page.getByRole("heading", { name: /Tashkent.*Namangan/ })).toBeVisible();
  await expect(page.getByLabel(/^Changes/)).toHaveValue("0");
  const results = page.getByRole("list", { name: "Journeys" }).getByRole("listitem");
  const testCard = results.filter({ hasText: "SynthRail TEST" }).first();
  const demoCard = results.filter({ hasText: "Demo price" }).first();
  await expect(testCard).toBeVisible();

  // Pick two journeys and compare them.
  await testCard.getByRole("checkbox", { name: /Compare/ }).check();
  await demoCard.getByRole("checkbox", { name: /Compare/ }).check();
  const tray = page.getByRole("region", { name: "Journeys selected for comparison" });
  await expect(tray).toContainText("2 of 4 selected");
  await tray.getByRole("link", { name: "Compare 2" }).click();
  await expect(page).toHaveURL(/\/compare\?ids=/);
  await expect(page.getByRole("heading", { name: "Compare journeys" })).toBeVisible();
  await expect(page.getByText("Demonstration data is included; its prices and times are not real.")).toBeVisible();
  // Desktop shows a table, phones show cards: check whichever is visible.
  await expect(page.getByText("Cheapest", { exact: true }).locator("visible=true").first()).toBeVisible();
  await expect(page.getByText("SynthRail TEST").locator("visible=true").first()).toBeVisible();

  // Open the bookable journey, register and save it.
  await page.goBack();
  await testCard.getByRole("link", { name: /View details/ }).click();
  await expect(page).toHaveURL(/\/journeys\/synthbook~/);
  const journeyUrl = page.url();
  await expect(page.getByRole("link", { name: "Go to provider" })).toBeVisible();
  await page.getByRole("link", { name: "Sign in to save" }).click();
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
  await page.getByLabel("Email").locator("visible=true").fill(email);
  await page.getByLabel("Password").locator("visible=true").fill("correct horse battery 9");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(journeyUrl);
  await page.getByRole("button", { name: "Save journey" }).click();
  await expect(page.getByRole("link", { name: /Saved/ })).toBeVisible();

  // Reopen it from the dashboard.
  await page.goto("/dashboard");
  const saved = page.getByRole("region", { name: /Saved journeys/ }).getByRole("listitem").first();
  await expect(saved).toContainText("Tashkent → Namangan");
  await saved.getByRole("link", { name: "View trip" }).click();
  await expect(page).toHaveURL(journeyUrl);

  // Booking hand-off: explained first, then the operator's own site.
  await page.getByRole("link", { name: "Go to provider" }).click();
  await expect(page.getByRole("heading", { name: "You're leaving T-Port" })).toBeVisible();
  await expect(page.getByText("booking.synthrail.test").first()).toBeVisible();
  await expect(page.getByText(/T-Port does not sell tickets/)).toBeVisible();
  await page.getByRole("link", { name: /Continue to booking\.synthrail\.test/ }).click();
  await expect(page.getByRole("heading", { name: "Operator booking page (test double)" })).toBeVisible();
  // T-Port sent the traveller to the operator's exact URL, with nothing added.
  expect(operatorUrl).toMatch(/^https:\/\/booking\.synthrail\.test\/book\?service=SBK101&date=\d{4}-\d{2}-\d{2}$/);
});

test("the assistant understands arrival deadlines and changes", async ({ page }) => {
  await page.goto("/planner");
  await page.getByLabel("Ask T-AI").fill("Tashkent to Bukhara tomorrow, arrive by 6 pm, fewest changes");
  await page.getByRole("button", { name: "Send" }).click();
  const understood = page.getByRole("list", { name: "Understood as" });
  await expect(understood).toContainText("arrive by 18:00");
  await expect(understood).toContainText("fewest changes");
  await expect(page.getByText(/Sorted by the fewest changes/)).toBeVisible();
  await page.getByRole("link", { name: /See all .* results with filters/ }).click();
  await expect(page).toHaveURL(/arrive_before=18%3A00/);
  await expect(page.getByLabel("Arrive by")).toHaveValue("18:00");
});

test("T-AI turns a request into recommended, cheapest, fastest and most direct picks", async ({ page }) => {
  await page.goto("/planner");
  await expect(page.getByRole("heading", { name: /T-AI/, level: 1 })).toBeVisible();
  await page.getByRole("button", { name: /Find the cheapest route from Tashkent to Samarkand/ }).click();
  const chat = page.getByRole("region", { name: "Conversation with T-AI" });
  await expect(chat.getByRole("link", { name: "Select route" })).toHaveCount(4);
  for (const name of ["Recommended", "Cheapest", "Fastest", "Fewest changes"]) {
    await expect(chat.getByRole("tab", { name })).toBeVisible();
  }
  await expect(chat.getByRole("region", { name: "T-AI insight" })).toContainText(/option\(s\)/);
  await chat.getByRole("tab", { name: /All options/ }).click();
  await expect(chat.getByRole("link", { name: "Select route" })).toHaveCount(0);
  await chat.getByRole("tab", { name: "Recommended" }).click();
  await chat.getByRole("link", { name: "Select route" }).first().click();
  await expect(page).toHaveURL(/\/journeys\//);
});
