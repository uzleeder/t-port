import { randomBytes } from "node:crypto";
import { deflateSync } from "node:zlib";
import { expect, test } from "@playwright/test";

/**
 * A real, decodable photo-sized PNG of random pixels: after the browser crops it to 512×512 it is
 * still well over the 64 KB that other API requests may send, like a real photo.
 */
function png(width = 900, height = 700): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, body: Buffer) => {
    const head = Buffer.alloc(4);
    head.writeUInt32BE(body.length);
    const typed = Buffer.concat([Buffer.from(type, "ascii"), body]);
    const tail = Buffer.alloc(4);
    tail.writeUInt32BE(crc(typed));
    return Buffer.concat([head, typed, tail]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr.set([8, 2, 0, 0, 0], 8);
  const raw = Buffer.concat(
    Array.from({ length: height }, () => Buffer.concat([Buffer.from([0]), randomBytes(width * 3)])),
  );
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

test("edit profile: upload a photo, change the name, remove the photo", async ({ page }, info) => {
  const email = `profile-${info.project.name}-${Date.now()}@example.test`;
  const res = await page.request.post("/api/v1/auth/register", {
    data: { email, password: "correct horse battery 9" },
  });
  expect(res.ok()).toBeTruthy();

  await page.goto("/profile");
  const card = page.getByRole("region", { name: email.split("@")[0] });
  await expect(card).toBeVisible();
  const headerPill = page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: /Dashboard for/ });
  await expect(headerPill.locator("img")).toHaveCount(0); // initial only

  await card.getByRole("button", { name: "Edit profile" }).click();
  await page.getByLabel("Choose a profile photo").setInputFiles({ name: "me.png", mimeType: "image/png", buffer: png() });
  await page.getByLabel("Name").fill("Aziza Karimova");
  await page.getByRole("button", { name: "Save", exact: true }).click();

  await expect(page.getByRole("status").filter({ hasText: "Profile saved." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Aziza Karimova" })).toBeVisible();
  await expect(headerPill.locator("img")).toHaveAttribute("src", /\/api\/v1\/me\/avatar\?v=\d+/);
  const photo = await page.request.get((await headerPill.locator("img").getAttribute("src"))!);
  expect(photo.status()).toBe(200);
  expect(photo.headers()["content-type"]).toMatch(/^image\/(webp|jpeg)$/);

  // Remove it again.
  await page.getByRole("button", { name: "Edit profile" }).click();
  await page.getByRole("button", { name: "Remove photo" }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Profile saved." })).toBeVisible();
  await expect(headerPill.locator("img")).toHaveCount(0);
});

test("a file that isn't a photo is refused with a clear message", async ({ page }, info) => {
  const email = `profile-bad-${info.project.name}-${Date.now()}@example.test`;
  await page.request.post("/api/v1/auth/register", { data: { email, password: "correct horse battery 9" } });
  await page.goto("/profile");
  await page.getByRole("button", { name: "Edit profile" }).click();
  await page
    .getByLabel("Choose a profile photo")
    .setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
  await expect(page.getByRole("alert").filter({ hasText: "Choose a photo" })).toBeVisible();
});
