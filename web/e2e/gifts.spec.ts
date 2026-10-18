import type { APIRequestContext, Page } from "@playwright/test";

import {
  asFarAsLocation,
  expect,
  freshNumber,
  pickInterests,
  signIn,
  signUpWoman,
  test,
  usernameAndAbout,
} from "./fixtures";

/**
 * J13 (06-TESTING), T-8.10's journey: a man sends a woman a free gift from
 * her profile, she finds it in the You tab and on her profile, and her switch
 * hides it from him.
 *
 * Both sign up through the screens, as J1 and J2 do. She is `signUpWoman`
 * (`fixtures.ts`, moved there for T-7.13's journey, P-663): her face photo
 * approved by the worker and her selfie matched by the real models, so
 * Chromium only (its fake camera). His steps here repeat J1's
 * (`signup.spec.ts`), with the shared helpers; sharing the rest is P-663. He
 * reaches her by her `/@username` link, which takes a signed-in man to the
 * in-app profile (T-6.8). Her page is the fixture's, watched for CSP
 * violations; his is watched the same way here.
 */

const WEB = "http://127.0.0.1:3100";
// Beside Model Town, Phagwara (P-38's areas).
const PHAGWARA = { latitude: 31.2139, longitude: 75.768 };
const PIN = "4719";

async function tapPin(page: Page, pin: string) {
  for (const digit of pin) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
}

/** A man into the app, as J1's twin: an area picked, no photo, no selfie. */
async function signUpMan(page: Page, request: APIRequestContext) {
  const phone = freshNumber();
  await signIn(page, request, phone);
  await asFarAsLocation(page, {
    gender: /^Man/,
    seeking: "Women",
    firstName: "Kabir",
  });
  await page.getByRole("button", { name: "Share my location" }).click();
  await expect(
    page.getByRole("heading", { name: "Pick your area" }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Model Town" }).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await usernameAndAbout(page, `kabir_${phone.slice(-6)}`);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/interests$/);
  await pickInterests(page);
  await tapPin(page, PIN);
  await expect(
    page.getByRole("heading", { name: "Confirm your PIN" }),
  ).toBeVisible();
  await tapPin(page, PIN);
  await expect(page).toHaveURL(/\/onboarding\/selfie$/);
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page).toHaveURL(/\/discover$/);
}

/** A reload with a PIN starts locked (T-3.10); his PIN opens it. */
async function unlock(page: Page) {
  await expect(
    page.getByRole("heading", { name: "Enter your PIN" }),
  ).toBeVisible();
  await tapPin(page, PIN);
  await expect(
    page.getByRole("heading", { name: "Enter your PIN" }),
  ).toHaveCount(0);
}

/**
 * Her profile in the app, reached by her link (T-6.8): a full page load, so
 * his session comes back locked, and his PIN opens it.
 */
async function openProfile(page: Page, username: string) {
  await page.goto(`/@${username}`);
  await expect(page).toHaveURL(/\/people\/[0-9a-f-]{36}$/);
  await unlock(page);
  await expect(
    page.getByRole("heading", { level: 1, name: /^Priya/ }),
  ).toBeVisible();
}

const giftsRow = (page: Page) =>
  page.getByRole("heading", { level: 2, name: "Gifts", exact: true });

test("J13: a man sends a free gift from her profile; she sees it, and hides it from him", async ({
  page,
  browser,
  context,
  request,
  browserName,
}) => {
  test.skip(
    browserName === "firefox",
    "her selfie needs Chromium's fake camera (playwright.config.ts)",
  );
  await context.grantPermissions(["geolocation", "camera"], { origin: WEB });
  await context.setGeolocation(PHAGWARA);
  const username = await signUpWoman(page, request);

  // Him, in a browser of his own, watched for CSP violations as hers is.
  const his = await browser.newContext({ baseURL: WEB });
  const him = await his.newPage();
  const violations: string[] = [];
  him.on("console", (message) => {
    if (message.text().includes("Content Security Policy")) {
      violations.push(message.text());
    }
  });
  await signUpMan(him, request);
  await openProfile(him, username);

  await him.getByRole("button", { name: "Gift", exact: true }).click();
  const sheet = him.getByRole("dialog", { name: "Send Priya a gift" });
  await expect(sheet).toContainText("15 free sends left this week");
  await sheet.getByRole("button", { name: "Coffee, Free" }).click();
  await sheet.getByRole("button", { name: "Send Coffee · Free" }).click();
  await expect(
    him.getByRole("status").filter({ hasText: "Coffee sent to Priya" }),
  ).toBeVisible();
  await expect(sheet).toHaveCount(0);
  // A free send moves no Vela: his 5 welcome Velas stand (D-231).
  await expect(
    him.getByRole("button", { name: "5 Velas. Buy Velas" }),
  ).toBeVisible();
  // Her counts, asked again by the send: one Coffee, never from whom.
  await expect(giftsRow(him)).toBeVisible();
  await expect(giftsRow(him).locator("..")).toContainText("1☕ Coffee");

  // Her You tab: who sent it, never a price.
  await page.goto("/you");
  await expect(
    page.getByRole("heading", { level: 2, name: "Gifts you've received" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Coffee from Kabir/ }),
  ).toBeVisible();
  await expect(page.locator("main")).not.toContainText(/Vela/);

  // Her switch off: his reload of her profile has no gifts row.
  const toggle = page.getByRole("switch", { name: "Show gifts on my profile" });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await him.reload();
  await unlock(him);
  await expect(
    him.getByRole("heading", { level: 1, name: /^Priya/ }),
  ).toBeVisible();
  await expect(giftsRow(him)).toHaveCount(0);

  await his.close();
  expect(violations, "no CSP violation on his pages").toEqual([]);
});
