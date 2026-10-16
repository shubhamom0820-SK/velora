import { expect, test } from "./fixtures";

/**
 * `/@username` (T-6.8, D-001, D-544), served through next.config's rewrite to
 * `/share/[username]`: a nonce route (D-541), never indexed, its canonical
 * address the `@` one. Nobody here turned a public link on, so every page says
 * it isn't public; the API's own tests hold what it shows when one is.
 */

test("/@username serves its page with a nonce, never indexed, as its own address", async ({
  page,
}) => {
  const response = await page.goto("/@nobody_here");

  expect(response?.status()).toBe(200);
  const policy = response?.headers()["content-security-policy"] ?? "";
  expect(policy).toMatch(/'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(policy).not.toContain("'unsafe-inline'");
  await expect(
    page.getByRole("heading", { name: "This profile isn't public" }),
  ).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    /noindex/,
  );
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/@nobody_here$/,
  );
  expect(page.url()).toMatch(/\/@nobody_here$/);
});

test("what follows an @ but isn't a username is no page", async ({ page }) => {
  const response = await page.goto("/@a!b");

  expect(response?.status()).toBe(404);
  await expect(
    page.getByRole("heading", { name: "This page isn't here" }),
  ).toBeVisible();
});
