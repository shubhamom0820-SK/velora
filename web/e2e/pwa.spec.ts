import { expect, test } from "./fixtures";

/**
 * T-9.7: the PWA, in a real browser against a production build. Signed out
 * throughout: the worker is on every page (D-1041), so no sign-in journey is
 * needed, and none spends an OTP send.
 *
 * The fixtures' watch fails the test on any CSP violation, so the offline
 * page's own policy (D-1040) is proved by what the browser refused: nothing.
 */

type Icon = { src: string; sizes: string };

test("links the manifest from every page, and its icons are there", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(href).toBe("/manifest.webmanifest");

  const response = await request.get("/manifest.webmanifest");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain(
    "application/manifest+json",
  );
  const manifest = (await response.json()) as {
    id: string;
    start_url: string;
    display: string;
    icons: Icon[];
  };
  expect(manifest).toMatchObject({
    id: "/",
    start_url: "/discover",
    display: "standalone",
  });
  expect(manifest.icons.map((icon) => icon.src)).toEqual([
    "/icons/icon-192.png",
    "/icons/icon-512.png",
    "/icons/icon-maskable-512.png",
  ]);
  for (const icon of manifest.icons) {
    const file = await request.get(icon.src);
    expect(file.status()).toBe(200);
    expect(file.headers()["content-type"]).toBe("image/png");
  }
});

test("registers the one worker on the landing page, past the HTTP cache", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const registration = await page.evaluate(async () => {
    const ready = await navigator.serviceWorker.ready;
    const all = await navigator.serviceWorker.getRegistrations();
    return {
      scope: ready.scope,
      script: ready.active?.scriptURL,
      updateViaCache: ready.updateViaCache,
      count: all.length,
    };
  });
  expect(registration).toEqual({
    scope: new URL("/", page.url()).href,
    script: new URL("/sw.js", page.url()).href,
    updateViaCache: "none",
    count: 1,
  });

  const worker = await request.get("/sw.js");
  expect(worker.headers()["cache-control"]).toBe("no-cache");
});

test("shows the offline page when the network is gone, and tries again from it", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  // The worker claims the open page as it activates; wait until it has.
  await expect
    .poll(() =>
      page.evaluate(() => navigator.serviceWorker.controller !== null),
    )
    .toBe(true);

  await context.setOffline(true);
  const offline = await page.goto("/privacy");
  expect(offline?.status()).toBe(503);
  await expect(
    page.getByRole("heading", { name: "You're offline" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/privacy$/);
  expect(await page.locator("script").count()).toBe(0);

  await context.setOffline(false);
  await page.getByRole("link", { name: "Try again" }).click();
  await expect(page).toHaveTitle(/Privacy/);
  await expect(
    page.getByRole("heading", { name: "You're offline" }),
  ).toHaveCount(0);
});
