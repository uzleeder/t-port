import { expect, test } from "@playwright/test";

test("T-AI artwork cycles colours without a picker and respects reduced motion", async ({ page }) => {
  await page.goto("/planner");
  await expect(page.getByRole("group", { name: "T-AI logo colour" })).toHaveCount(0);
  await page.goto("/");
  const showcase = page.locator('section[aria-labelledby="ai-h"]');
  await expect(showcase.getByRole("group", { name: "T-AI logo colour" })).toHaveCount(0);
  const artwork = showcase.locator(".tai-original-art").first();
  await expect(artwork).toHaveAttribute("href", "/images/t-ai/neural-arrow-reference.png");
  await expect(artwork).toHaveCSS("animation-name", "none");
  await expect(showcase.locator(".tai-neural-motion").first()).toHaveCSS("display", "none");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(artwork).toHaveCSS("animation-name", "tai-colour-cycle");
  await expect(showcase.locator(".tai-logo").first()).toHaveCSS("animation-name", "tai-wave");
  await expect(showcase.locator(".tai-neural-motion").first()).toHaveCSS("display", "inline");
});

test("T-AI answers questions about places from its knowledge, with sources", async ({ page }) => {
  await page.goto("/planner");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("T-AI");
  const chat = page.getByRole("region", { name: "Conversation with T-AI" });
  await page.getByLabel("Ask T-AI").fill("What can I see in Khiva?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(chat).toContainText("Here's what I know about Khorezm: Itchan Kala and Kalta Minor.");
  const itchan = chat.getByRole("article", { name: "Itchan Kala" });
  await expect(itchan).toContainText("UNESCO");
  await expect(itchan.getByRole("link", { name: "whc.unesco.org" })).toHaveAttribute(
    "href",
    "https://whc.unesco.org/en/list/543",
  );
  await expect(itchan.getByRole("link", { name: /Journeys to Khiva/ })).toBeVisible();
  // No route yet: T-AI offers to plan one.
  await expect(chat).toContainText("Want to go there? Tell me where you're starting from and when.");
});

test("T-AI answers in Uzbek when asked in Uzbek", async ({ page }) => {
  await page.goto("/planner");
  await page.getByLabel("Ask T-AI").fill("Registon haqida aytib bering");
  await page.getByRole("button", { name: "Send" }).click();
  const chat = page.getByRole("region", { name: "Conversation with T-AI" });
  await expect(chat).toContainText("Registon maydoni haqida bilganlarim:");
  await expect(chat.getByRole("article", { name: "Registon maydoni" })).toContainText("Tarix va ahamiyat");
});

test("Ask T-AI from an Explore place opens the chat with the answer", async ({ page }) => {
  await page.goto("/explore/samarkand");
  await page
    .getByRole("article", { name: "Registan Square" })
    .getByRole("link", { name: "Ask T-AI" })
    .click();
  await expect(page).toHaveURL(/\/planner$/);
  const chat = page.getByRole("region", { name: "Conversation with T-AI" });
  await expect(chat).toContainText("Tell me about Registan Square");
  await expect(chat.getByRole("article", { name: "Registan Square" })).toContainText("Ulugh Beg");
});
