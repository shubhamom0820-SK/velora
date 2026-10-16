import type { Page } from "@playwright/test";

import { expect, test } from "./fixtures";

/**
 * P-445, D-980: every 404 is our page, not Next's built-in one, whose inline
 * styles neither CSP allows (five style-src violations at `/no-such-page`, 8
 * October 2026), and it renders per request, so beneath a nonce route it
 * carries the request's nonce (prerendered, every script on it was refused, 16
 * October 2026). The fixtures' watch fails either case on any violation, so
 * each is proved by what the browser refused: nothing.
 */

/**
 * The page hydrated: its link home navigates on the client, so what was set
 * on `window` before the tap is still there after it. Unhydrated, the link is
 * a plain one, the document loads again, and the mark is gone.
 */
async function goesHomeOnTheClient(page: Page) {
  await page.evaluate(() => {
    (window as unknown as { __before: boolean }).__before = true;
  });
  await page.getByRole("link", { name: /^Go to / }).click();
  await expect(page).toHaveURL(/127\.0\.0\.1:3100\/$/);
  expect(
    await page.evaluate(
      () => (window as unknown as { __before?: boolean }).__before,
    ),
  ).toBe(true);
}

test("an address that isn't a page is ours, under the static policy", async ({
  page,
}) => {
  const response = await page.goto("/no-such-page");

  expect(response?.status()).toBe(404);
  expect(response?.headers()["content-security-policy"]).toContain(
    "'unsafe-inline'",
  );
  await expect(
    page.getByRole("heading", { name: "This page isn't here" }),
  ).toBeVisible();
  await goesHomeOnTheClient(page);
});

// Beneath a nonce route (the proxy's `/login/:path*`), where no page matches.
// Not `/onboarding/<no such step>`: its gate streams "Loading" first, so that
// answer is a 200 before the step's 404 can be.
test("an address beneath a nonce route that isn't a page is ours, under the nonce policy", async ({
  page,
}) => {
  const response = await page.goto("/login/no-such-page");

  expect(response?.status()).toBe(404);
  const policy = response?.headers()["content-security-policy"] ?? "";
  expect(policy).toMatch(/'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(policy).not.toContain("'unsafe-inline'");
  await expect(
    page.getByRole("heading", { name: "This page isn't here" }),
  ).toBeVisible();
  await goesHomeOnTheClient(page);
});
