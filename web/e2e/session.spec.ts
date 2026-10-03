import { expect, freshNumber, signIn, test } from "./fixtures";

/**
 * T-3.10's session machinery, on every push (T-3.13): seen once by hand in
 * Chrome, kept here so it stays true. Locally it proves the mechanism;
 * staging's platform is T-3.14's to prove.
 */

const API = "http://127.0.0.1:8100";

/**
 * Both auth cookies from the whole jar. Not `cookies(url)`: for an `http://`
 * URL Playwright withholds `Secure` cookies, which the browser itself does send
 * to 127.0.0.1, so a filtered read is always empty, and a check that it's empty
 * could never fail.
 */
async function authCookies(page: import("@playwright/test").Page) {
  const cookies = (await page.context().cookies()).filter(
    (c) => c.domain === new URL(API).hostname,
  );
  return Object.fromEntries(
    cookies
      .filter((c) => c.name === "refresh_local" || c.name === "csrf_local")
      .map((c) => [c.name, c.value]),
  );
}

test("a reload restores the session, and each refresh rotates both cookies", async ({
  page,
  request,
}) => {
  await signIn(page, request, freshNumber());
  const signedIn = await authCookies(page);
  expect(Object.keys(signedIn).sort()).toEqual(["csrf_local", "refresh_local"]);

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "When were you born?" }),
  ).toBeVisible();
  const restored = await authCookies(page);
  expect(restored.refresh_local).not.toBe(signedIn.refresh_local);
  expect(restored.csrf_local).not.toBe(signedIn.csrf_local);

  // The next refresh carries the rotated values: were it the old ones, this
  // would be reuse, and the session would end (D-067).
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "When were you born?" }),
  ).toBeVisible();
  expect((await authCookies(page)).refresh_local).not.toBe(
    restored.refresh_local,
  );
});

test("two tabs reloaded together both stay signed in", async ({
  page,
  request,
}) => {
  await signIn(page, request, freshNumber());
  const second = await page.context().newPage();
  await second.goto("/onboarding/birthday");
  await expect(
    second.getByRole("heading", { name: "When were you born?" }),
  ).toBeVisible();

  await Promise.all([page.reload(), second.reload()]);

  for (const tab of [page, second]) {
    await expect(
      tab.getByRole("heading", { name: "When were you born?" }),
    ).toBeVisible();
    await expect(tab).toHaveURL(/\/onboarding\/birthday$/);
  }
  // And neither signed the other out: a third load still restores.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "When were you born?" }),
  ).toBeVisible();
});

test("sign-out clears both cookies, and a reload lands on /login", async ({
  page,
  request,
}) => {
  await signIn(page, request, freshNumber());

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  expect(await authCookies(page)).toEqual({});
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "What's your number?" }),
  ).toBeVisible();
});
