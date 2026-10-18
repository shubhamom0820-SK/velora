import { join, resolve } from "node:path";

import {
  expect,
  test as base,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

export { expect };

const API = "http://127.0.0.1:8100";

/**
 * Each browser context is a client of its own (P-680, D-890): the E2E API
 * (api/tests/e2e_server.py) reads the client's address from this header, so
 * each person in a journey has D-066's 20 OTP sends an hour, as each phone
 * does, where read from the socket they would all be 127.0.0.1 and share them.
 * Added to the API's requests only: the local S3's CORS admits Content-Type
 * alone (infra/s3/private-cors.xml), so on a photo's PUT it would fail the
 * upload. A deployed API never reads it (`PROXY_CLIENT_IP_HEADERS`).
 */
const CLIENT_IP_HEADER = "X-E2E-Client-IP";
const addressed = new WeakSet<BrowserContext>();
let addresses = 0;

/** An address in 198.18.0.0/15 (RFC 2544's, never a real client's), once a context. */
async function ownAddress(
  context: BrowserContext,
  workerIndex: number,
): Promise<void> {
  if (addressed.has(context)) return;
  addressed.add(context);
  addresses += 1;
  if (addresses > 254 || workerIndex > 255) {
    throw new Error("e2e: out of client addresses (198.18.<worker>.<1-254>)");
  }
  const address = `198.18.${workerIndex}.${addresses}`;
  await context.route(`${API}/**`, (route) =>
    route.continue({
      headers: { ...route.request().headers(), [CLIENT_IP_HEADER]: address },
    }),
  );
}

let issued = 0;

/** A mobile number no other journey in this run uses: "98" and eight digits. */
export function freshNumber(): string {
  const n = (Date.now() + issued++) % 100_000_000;
  return `98${String(n).padStart(8, "0")}`;
}

/**
 * The code the fake SMS last sent the number, as its phone would have it, or
 * null if it never sent one (api/app/modules/e2e). Asked from Node, never the
 * page: the browser has no business with this endpoint.
 */
export async function codeFor(
  request: APIRequestContext,
  phone: string,
): Promise<string | null> {
  const response = await request.post(`${API}/v1/test/sms/last-code`, {
    data: { phone },
  });
  expect(response.status()).toBe(200);
  return ((await response.json()) as { code: string | null }).code;
}

/** Sign in through the screens, as a person would, ending on the birthday step. */
export async function signIn(
  page: Page,
  request: APIRequestContext,
  phone: string,
): Promise<string> {
  await page.goto("/login");
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(
    page.getByRole("heading", { name: "Enter the code" }),
  ).toBeVisible();
  const code = await codeFor(request, phone);
  expect(code).toMatch(/^[0-9]{6}$/);
  // The phone's autofill puts all six into the first box.
  await page.getByRole("textbox", { name: "Digit 1 of 6" }).fill(code ?? "");
  await expect(page).toHaveURL(/\/onboarding\/birthday$/);
  return code ?? "";
}

const PIN = "4719";
const INTERESTS = ["Filter coffee", "Trekking", "Reading", "Cricket", "Travel"];

async function tapPin(page: Page, pin: string) {
  for (const digit of pin) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
}

/**
 * Unlocks the app after a full load, which locks it again (T-3.9), with the
 * PIN `signUpMan` set.
 */
export async function unlock(page: Page) {
  const lock = page.getByRole("heading", { name: "Enter your PIN" });
  await expect(lock).toBeVisible();
  await tapPin(page, PIN);
  await expect(lock).toHaveCount(0);
}

/**
 * A new man, through every onboarding screen, into the app (J1's way,
 * shortened: an area picked, no photo, no selfie). His username, which is
 * his number's last six digits after his first name, lower-cased, and `_`
 * (`kabir_` unless a journey names him: T-7.13's deck tells people apart by
 * the name on the card).
 */
export async function signUpMan(
  page: Page,
  context: BrowserContext,
  request: APIRequestContext,
  firstName = "Kabir",
): Promise<string> {
  await context.clearPermissions();
  const phone = freshNumber();
  await signIn(page, request, phone);

  await page.getByLabel("Date of birth").fill("1998-03-02");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes, that's right" }).click();
  await expect(page).toHaveURL(/\/onboarding\/gender$/);
  await page.getByRole("radio", { name: /^Man/ }).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/looking-for$/);
  await page.getByRole("button", { name: "Women", exact: true }).click();
  await page.getByRole("button", { name: "Something serious" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/name$/);
  await page.getByLabel("First name").fill(firstName);
  await page.getByLabel("Hometown, where you're from").fill("Jalandhar");
  await page.getByLabel("Where you live now").fill("Phagwara");
  await page.getByRole("button", { name: "Continue" }).click();

  // No position shared: he picks an area, as J1's twin does.
  await expect(page).toHaveURL(/\/onboarding\/location$/);
  await page.getByRole("button", { name: "Share my location" }).click();
  await expect(
    page.getByRole("heading", { name: "Pick your area" }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Model Town" }).check();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/username$/);
  const username = `${firstName.toLowerCase()}_${phone.slice(-6)}`;
  await page.getByLabel("Username").fill(username);
  await expect(page.getByText("That one's free.")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/about$/);
  await page
    .getByLabel("About you")
    .fill("Cricket on Sundays and chai with too much ginger.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/photos$/);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/interests$/);
  for (const label of INTERESTS) {
    await page.getByRole("button", { name: label, exact: true }).click();
  }
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/pin$/);
  await tapPin(page, PIN);
  await expect(
    page.getByRole("heading", { name: "Confirm your PIN" }),
  ).toBeVisible();
  await tapPin(page, PIN);
  await expect(page).toHaveURL(/\/onboarding\/selfie$/);
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page).toHaveURL(/\/discover$/);
  return username;
}

// Her face photo is the 2021 portrait; Chromium's fake camera plays the 2017
// one (playwright.config.ts), so the real models compare one person's two.
const FACES = resolve(__dirname, "../../api/tests/fixtures/faces");

/** Birthday to Name, ending on the location question. */
export async function asFarAsLocation(
  page: Page,
  who: { gender: RegExp; seeking: string; firstName: string },
) {
  await page.getByLabel("Date of birth").fill("2000-01-15");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes, that's right" }).click();
  await expect(page).toHaveURL(/\/onboarding\/gender$/);
  await page.getByRole("radio", { name: who.gender }).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/looking-for$/);
  await page.getByRole("button", { name: who.seeking, exact: true }).click();
  await page.getByRole("button", { name: "Something serious" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/name$/);
  await page.getByLabel("First name").fill(who.firstName);
  await page.getByLabel("Hometown, where you're from").fill("Jalandhar");
  await page.getByLabel("Where you live now").fill("Phagwara");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/location$/);
}

/** Username and About, from the username step to the photos step. */
export async function usernameAndAbout(page: Page, username: string) {
  await expect(page).toHaveURL(/\/onboarding\/username$/);
  await page.getByLabel("Username").fill(username);
  await expect(page.getByText("That one's free.")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/about$/);
  await page
    .getByLabel("About you")
    .fill("Pottery on weekends, street food on weeknights.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/photos$/);
}

export async function pickInterests(page: Page) {
  for (const label of INTERESTS) {
    await page.getByRole("button", { name: label, exact: true }).click();
  }
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/pin$/);
}

/**
 * A woman all the way into the app, as J2 (P-663: moved here from J13's
 * `gifts.spec.ts`, T-7.13): her position shared, which the journey grants
 * first, her face photo approved by the worker and her selfie matched by the
 * real models, so Chromium only (its fake camera); no PIN. Her username, her
 * first name lower-cased (`priya` unless a journey names her), `_` and her
 * number's last six digits.
 */
export async function signUpWoman(
  page: Page,
  request: APIRequestContext,
  firstName = "Priya",
): Promise<string> {
  const phone = freshNumber();
  const username = `${firstName.toLowerCase()}_${phone.slice(-6)}`;
  await signIn(page, request, phone);
  await asFarAsLocation(page, {
    gender: /^Woman/,
    seeking: "Men",
    firstName,
  });
  await page.getByRole("button", { name: "Share my location" }).click();
  await usernameAndAbout(page, username);

  const chooser = page.waitForEvent("filechooser");
  await page
    .getByRole("button", { name: "Add your face photo", exact: true })
    .click();
  await (await chooser).setFiles(join(FACES, "chari_2021.jpg"));
  await expect(
    page.getByRole("region", { name: "Your face photo" }),
  ).toContainText("Face photo approved", { timeout: 30_000 });
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/interests$/);
  await pickInterests(page);
  await page.getByRole("button", { name: "Skip, I'll set it later" }).click();

  await expect(page).toHaveURL(/\/onboarding\/selfie$/);
  await page.getByRole("button", { name: "Open camera" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Face the camera in good light" }),
  ).toBeVisible();
  // A frame on screen before the shutter, as J2 waits for one.
  await page.evaluate(
    () =>
      new Promise<void>((presented) => {
        document
          .querySelector("video")
          ?.requestVideoFrameCallback(() => presented());
      }),
  );
  await page.getByRole("button", { name: "Take selfie" }).click();
  await page.getByRole("button", { name: "Use this selfie" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Your selfie matched your face photo." }),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/discover$/);
  return username;
}

type Watch = {
  /** Every URL the page went to, for "no phone number in a URL" (D-080). */
  urls: string[];
};

/**
 * Every journey fails on any CSP violation (P-41's lesson: an inline style or
 * zod's eval probe works under `next dev` and is blocked in production), and
 * records the URLs it visited.
 */
export const test = base.extend<
  Watch & { cspViolations: string[]; addressed: void }
>({
  context: async ({ context }, provide, testInfo) => {
    await ownAddress(context, testInfo.workerIndex);
    await provide(context);
  },
  // And every context a journey opens itself (a second person's browser), so
  // none can be forgotten into the header-less bucket.
  addressed: [
    async ({ browser }, provide, testInfo) => {
      const newContext = browser.newContext;
      browser.newContext = async (options) => {
        const context = await newContext.call(browser, options);
        await ownAddress(context, testInfo.workerIndex);
        return context;
      };
      await provide();
      browser.newContext = newContext;
    },
    { auto: true },
  ],
  cspViolations: [
    async ({ page }, provide) => {
      const violations: string[] = [];
      await page.addInitScript(() => {
        document.addEventListener("securitypolicyviolation", (event) => {
          console.error(
            `CSP-VIOLATION ${event.violatedDirective} ${event.blockedURI}`,
          );
        });
      });
      page.on("console", (message) => {
        const text = message.text();
        if (
          text.startsWith("CSP-VIOLATION") ||
          text.includes("Content Security Policy")
        ) {
          violations.push(text);
        }
      });
      await provide(violations);
      expect(violations, "no CSP violation on any page").toEqual([]);
    },
    { auto: true },
  ],
  urls: async ({ page }, provide) => {
    const urls: string[] = [];
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) urls.push(frame.url());
    });
    await provide(urls);
  },
});
