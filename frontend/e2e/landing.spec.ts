import { expect, test } from "@playwright/test";

test.describe("intro", () => {
  test.use({ reducedMotion: "no-preference" });

  test("plays once per session, can be skipped, and never blocks the page afterwards", async ({ page }) => {
    await page.goto("/", { waitUntil: "commit" });
    await expect(page.locator("html")).toHaveAttribute("data-intro", "play");
    const skip = page.getByRole("button", { name: "Skip intro" });
    await skip.click({ timeout: 1500 }); // the intro lasts ~2.3 s
    await expect(skip).toBeHidden();
    await expect(page.locator("html")).not.toHaveAttribute("data-intro", /.*/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("button", { name: "Skip intro" })).toBeHidden(); // same session: no replay
  });

  test("ends by itself", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Skip intro" })).toBeHidden({ timeout: 5000 });
    await page.getByRole("link", { name: /Explore T-PORT/ }).click();
    await expect(page).toHaveURL(/#explore$/);
  });
});

test("reduced motion: no intro at all", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Skip intro" })).toBeHidden();
  await expect(page.locator("html")).not.toHaveAttribute("data-intro", /.*/);
});

test("switches language between English, Uzbek and Russian, and remembers it", async ({ page }, info) => {
  await page.goto("/");
  // Hidden languages stay in the DOM; the accessible name is what is shown.
  const h1 = page.getByRole("heading", { level: 1 });
  await expect(h1).toHaveAccessibleName("One Destination. Every Way to Get There.");
  // Found by place, not name: the picker's own label is translated too ("Til", "Язык").
  const where = info.project.name === "mobile" ? page.locator("footer") : page.getByRole("navigation", { name: "Main" });
  const select = where.locator("select:visible");
  await expect(select).toHaveAccessibleName("Language");
  await select.selectOption("uz");
  await expect(h1).toHaveAccessibleName("Bitta manzil. Unga yetib borishning barcha yo‘llari.");
  await expect(page.getByRole("button", { name: "Yo‘nalishlarni qidirish" })).toBeVisible();
  await expect(select).toHaveAccessibleName("Til");
  await select.selectOption("ru");
  await expect(h1).toHaveAccessibleName("Одна цель. Все пути к ней.");
  await page.reload();
  await expect(h1).toHaveAccessibleName("Одна цель. Все пути к ней.");
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
});

test("all 14 regions link to their pages", async ({ page }) => {
  await page.goto("/");
  const explore = page.getByRole("region", { name: "Explore Uzbekistan." });
  await expect(explore.getByRole("listitem")).toHaveCount(14);
  await explore.getByRole("link", { name: /Khorezm/ }).click();
  await expect(page).toHaveURL(/\/explore\/khorezm$/);
});

test("multimodal search allows combined modes with up to two changes", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: /Multimodal/ }).check({ force: true });
  await page.getByRole("combobox", { name: "From" }).fill("Tashkent");
  await page.getByRole("option", { name: /^Tashkent/ }).first().click();
  await page.getByRole("combobox", { name: "To" }).fill("Khiva");
  await page.getByRole("option", { name: /Khiva/ }).first().click();
  await page.getByRole("button", { name: "Swap origin and destination" }).click();
  await expect(page.getByRole("combobox", { name: "From" })).toHaveValue(/Khiva/);
  await page.getByRole("button", { name: "Search journeys" }).click();
  await expect(page).toHaveURL(/origin=khiva&destination=tashkent.*max_transfers=2/);
});

test("the T-AI showcase uses real search results and labels demo data", async ({ page }) => {
  await page.goto("/");
  const preview = page.getByRole("group", { name: "T-AI chat preview" });
  await expect(preview).toContainText("Cheapest journey");
  await expect(preview).toContainText("Fastest journey");
  await expect(preview).toContainText("Recommended journey");
  await expect(preview).toContainText("Demonstration data");
  await preview.getByRole("link", { name: "Ask T-AI this" }).click();
  await expect(page.getByRole("region", { name: "Conversation with T-AI" })).toContainText("Find the best way");
});

test("roadmap marks future markets as planned", async ({ page }) => {
  await page.goto("/");
  const about = page.getByRole("region", { name: "From Uzbekistan to the World." });
  await expect(about).toContainText("Pilot now");
  await expect(about).toContainText("Planned");
  await expect(about).toContainText("plans, not live services");
});

test("phone menu opens, navigates and closes", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await page.goto("/");
  const menu = page.getByRole("button", { name: "Menu" });
  await menu.click();
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "How It Works", exact: true }).click();
  await expect(page).toHaveURL(/#how-it-works$/);
  await expect(page.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
});
