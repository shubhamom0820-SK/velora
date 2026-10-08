import { join, resolve } from "node:path";

import { type Locator, type Page } from "@playwright/test";

import { codeFor, expect, freshNumber, signIn, test } from "./fixtures";

/**
 * J1, J2 and J3 (06-TESTING), on Path B with the fake SMS (T-3.13, T-4.9).
 *
 * J1 and J2 run the whole of onboarding against the whole stack. From
 * T-4.12 (D-391, D-392) neither uploads a public photo: he leaves the photos
 * step with none; she uploads her face photo, the one her selfie is compared
 * with, to the local S3, checked by the worker and approved, private; then
 * her selfie from Chromium's fake camera (playwright.config.ts), compared
 * with it by the real models (D-088, D-330), and sign-up finished by T-4.8's
 * endpoint. The faces are NASA's public-domain portraits
 * (api/tests/fixtures/faces): her face photo is Raja Chari's 2021 portrait
 * and the camera plays his 2017 one, so the match is between two photos of
 * one person, which is what the models decide. The names are the test's own.
 *
 * J1 shares a position in Phagwara (T-4.10): the browser hands it over only
 * because the Permissions-Policy allows `geolocation=(self)`, so this is the
 * policy proved by its effect. Its twin is refused, and picks an area. J2's
 * camera opens under `camera=(self)` the same way (T-4.7).
 */

const WEB = "http://127.0.0.1:3100";
// Beside Model Town, Phagwara (P-38's areas).
const PHAGWARA = { latitude: 31.2139, longitude: 75.768 };
const FACES = resolve(__dirname, "../../api/tests/fixtures/faces");
// D-069 allows it: not a run, not a pair, not one of the common twenty.
const PIN = "4719";
// Five of the catalogue's labels (src/i18n/en.ts, P-26).
const INTERESTS = ["Filter coffee", "Trekking", "Reading", "Cricket", "Travel"];

type Person = {
  gender: RegExp;
  seeking: string;
  firstName: string;
  hometown: string;
  city: string;
  username: string;
  about: string;
  /** The profile photo, in FACES. */
  photo: string;
};

const ARJUN: Person = {
  gender: /^Man/,
  seeking: "Women",
  firstName: "Arjun",
  hometown: "Jalandhar",
  city: "Phagwara",
  username: "arjun",
  about: "Weekend trekker, filter coffee loyalist, and slow reader of novels.",
  photo: "williams_2004.jpg",
};

const PRIYA: Person = {
  gender: /^Woman/,
  seeking: "Men",
  firstName: "Priya",
  hometown: "Ludhiana",
  city: "Phagwara",
  username: "priya",
  about:
    "Pottery on weekends, street food on weeknights, and a dog called Momo.",
  photo: "chari_2021.jpg",
};

/** Birthday to Name, ending on the location question. */
async function asFarAsLocation(page: Page, who: Person) {
  await page.getByLabel("Date of birth").fill("2000-01-15");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "You were born on 15 January 2000.",
  );
  await page.getByRole("button", { name: "Yes, that's right" }).click();

  await expect(page).toHaveURL(/\/onboarding\/gender$/);
  await page.getByRole("radio", { name: who.gender }).check();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/looking-for$/);
  // Exactly: "Men" is also in "Women".
  await page.getByRole("button", { name: who.seeking, exact: true }).click();
  await page.getByRole("button", { name: "Something serious" }).click();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/name$/);
  await page.getByLabel("First name").fill(who.firstName);
  await page.getByLabel("Hometown, where you're from").fill(who.hometown);
  await page.getByLabel("Where you live now").fill(who.city);
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/location$/);
  await expect(
    page.getByRole("heading", { name: "Where are you?" }),
  ).toBeVisible();
}

/** Username and About, from the username step to the photos step. */
async function usernameAndAbout(page: Page, who: Person, phone: string) {
  await expect(page).toHaveURL(/\/onboarding\/username$/);
  await page.getByLabel("Username").fill(`${who.username}_${phone.slice(-6)}`);
  await expect(page.getByText("That one's free.")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/about$/);
  await page.getByLabel("About you").fill(who.about);
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/photos$/);
  await expect(
    page.getByRole("heading", { name: "Add your photos" }),
  ).toBeVisible();
}

/**
 * Her face photo (T-4.12, D-391), chosen as a person does, through its own
 * slot's picker: up to the local S3 by the presigned PUT, checked by the
 * worker (T-4.4, the fake moderation) and approved, private. No public photo
 * at all (D-392): the grid stays empty, and Continue leaves the step by its
 * own exit, which a woman may take once the face photo is there. Then on to
 * the interests.
 */
async function addFacePhoto(page: Page, file: string) {
  const chooser = page.waitForEvent("filechooser");
  // `exact`: the footer's disabled "Add your face photo to continue" would
  // match the name too, and never become clickable.
  await page
    .getByRole("button", { name: "Add your face photo", exact: true })
    .click();
  await (await chooser).setFiles(join(FACES, file));

  const slot = page.getByRole("region", { name: "Your face photo" });
  await expect(slot).toContainText("Face photo approved", { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Add a photo" })).toHaveCount(
    6,
  );
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/interests$/);
}

/** No photo of any kind (D-392): a man leaves the step with the grid empty. */
async function noPhoto(page: Page) {
  await expect(page.getByRole("button", { name: "Add a photo" })).toHaveCount(
    6,
  );
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/interests$/);
}

/** Exactly five (T-3.8), then on to the PIN. */
async function pickInterests(page: Page) {
  for (const label of INTERESTS) {
    await page.getByRole("button", { name: label, exact: true }).click();
  }
  await expect(page.getByText("5/5 chosen")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/pin$/);
}

/** Four taps on the keypad (the PIN step's and the lock's, T-3.10, T-3.12). */
async function tapPin(page: Page, pin: string) {
  for (const digit of pin) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
}

/**
 * A restored session with a PIN starts locked wherever it lands, an
 * onboarding step included (T-3.10): a full page load is a restore, a sign-in
 * by code isn't. The PIN opens it.
 */
async function unlock(page: Page, pin: string) {
  await expect(
    page.getByRole("heading", { name: "Enter your PIN" }),
  ).toBeVisible();
  await tapPin(page, pin);
  await expect(
    page.getByRole("heading", { name: "Enter your PIN" }),
  ).toHaveCount(0);
}

async function atTheSelfieStep(page: Page) {
  await expect(page).toHaveURL(/\/onboarding\/selfie$/);
  await expect(
    page.getByRole("heading", { name: "Quick selfie check" }),
  ).toBeVisible();
}

/** The app is barred until sign-up is done: /discover sends them back. */
async function barredFromTheApp(page: Page) {
  await page.goto("/discover");
  await expect(page).toHaveURL(/\/onboarding\/selfie$/);
}

/** In the app: Discover, inside the shell with its four-link nav (T-5.6). */
async function inTheApp(page: Page) {
  await expect(page).toHaveURL(/\/discover$/);
  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link"),
  ).toHaveCount(4);
}

/** Outside the app there is no shell: no nav in the page at all (T-5.6). */
async function noShell(page: Page) {
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
}

/** The box a browser drew, which must exist. */
async function boxOf(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box, "drawn on the page").not.toBeNull();
  return box ?? { x: 0, y: 0, width: 0, height: 0 };
}

/**
 * The shell where a browser draws it, at this project's width (P-82). T-5.6's
 * tests run in jsdom, which applies no CSS, and Tailwind drops a class it
 * can't compile without an error: only here does a lost style show. On a
 * phone the nav is the screen's bottom edge and the page's last line stays
 * clear of it; from 768 px it sits in the header's row.
 */
async function shellWhereItBelongs(page: Page) {
  const { width, height } = page.viewportSize() ?? { width: 0, height: 0 };
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link")).toHaveCount(4);
  for (const link of await nav.getByRole("link").all()) {
    await expect(link).toBeVisible();
  }
  const navBox = await boxOf(nav);
  const header = await boxOf(page.locator("header"));
  const inHeader =
    navBox.x >= header.x &&
    navBox.y >= header.y &&
    navBox.x + navBox.width <= header.x + header.width &&
    navBox.y + navBox.height <= header.y + header.height;
  if (width >= 768) {
    expect(inHeader, "the nav inside the header's box").toBe(true);
    return;
  }
  expect(inHeader, "the nav out of the header").toBe(false);
  expect(navBox.y + navBox.height, "the nav on the bottom edge").toBe(height);
  // At the page's end, where its last line meets the nav: scrolled and
  // measured in one step. Done in two, CI once read 1100 against the nav's
  // 788 (8 October 2026): the page wasn't at its end when measured, most
  // likely one still filling in. Under a pixel is the scroll's rounding
  // (788.05 seen locally); a lost padding is the nav's whole height.
  const contentEnd = await page.locator("main").evaluate((main) => {
    window.scrollTo(0, document.documentElement.scrollHeight);
    return (
      main.getBoundingClientRect().bottom -
      parseFloat(getComputedStyle(main).paddingBottom)
    );
  });
  expect(
    contentEnd,
    `the page's content ends above the nav, on ${page.url()}`,
  ).toBeLessThan(navBox.y + 1);
}

/** Each of the four places, opened from the nav, with the shell in place. */
async function everyPlaceFromTheNav(page: Page) {
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const [name, path] of [
    ["Chats", /\/chats$/],
    ["Wallet", /\/wallet$/],
    ["You", /\/you$/],
    ["Discover", /\/discover$/],
  ] as const) {
    await nav.getByRole("link", { name }).click();
    await expect(page).toHaveURL(path);
    await shellWhereItBelongs(page);
  }
}

test("J1: a new man signs up all the way to Discover, with no selfie", async ({
  page,
  context,
  request,
  urls,
}) => {
  await context.grantPermissions(["geolocation"], { origin: WEB });
  await context.setGeolocation(PHAGWARA);
  const phone = freshNumber();
  // The control for P-82's checks: no shell before he's in the app.
  await page.goto("/login");
  await expect(page.getByLabel("Mobile number")).toBeVisible();
  await noShell(page);
  await signIn(page, request, phone);
  await noShell(page);
  await asFarAsLocation(page, ARJUN);

  await page.getByRole("button", { name: "Share my location" }).click();

  await usernameAndAbout(page, ARJUN, phone);
  await noPhoto(page);
  await pickInterests(page);

  // A PIN, set and confirmed (T-3.12).
  await expect(
    page.getByRole("heading", { name: "Set a 4-digit PIN" }),
  ).toBeVisible();
  await tapPin(page, PIN);
  await expect(
    page.getByRole("heading", { name: "Confirm your PIN" }),
  ).toBeVisible();
  await tapPin(page, PIN);

  // A man may skip the selfie (D-008), and not before then is he in the app.
  // The visit to /discover is a full load, so his lock comes first.
  await atTheSelfieStep(page);
  await expect(
    page.getByRole("button", { name: "Skip for now" }),
  ).toBeVisible();
  await barredFromTheApp(page);
  await unlock(page, PIN);
  await page.getByRole("button", { name: "Skip for now" }).click();
  // His welcome Velas, granted by the API as he finished (T-8.11, D-470).
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "5 Velas are in your wallet, to start you off." }),
  ).toBeVisible();
  await inTheApp(page);

  // And again after a reload, in the app this time.
  await page.reload();
  await unlock(page, PIN);
  await inTheApp(page);

  // The shell where the browser draws it, on each of its four places (P-82).
  await everyPlaceFromTheNav(page);

  // D-080: the number never went in a URL.
  expect(urls.filter((url) => url.includes(phone.slice(-8)))).toEqual([]);
});

test("J2: a new woman is held at the selfie until it matches her face photo", async ({
  page,
  context,
  request,
  urls,
  browserName,
}) => {
  test.skip(
    browserName === "firefox",
    "the fake camera is Chromium's (playwright.config.ts)",
  );
  await context.grantPermissions(["geolocation", "camera"], { origin: WEB });
  await context.setGeolocation(PHAGWARA);
  const phone = freshNumber();
  await signIn(page, request, phone);
  await asFarAsLocation(page, PRIYA);

  await page.getByRole("button", { name: "Share my location" }).click();

  await usernameAndAbout(page, PRIYA, phone);
  await addFacePhoto(page, PRIYA.photo);
  await pickInterests(page);
  await page.getByRole("button", { name: "Skip, I'll set it later" }).click();

  // No way past the selfie for a woman (D-008): no skip, and the app barred.
  await atTheSelfieStep(page);
  await expect(page.getByRole("button", { name: "Open camera" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Skip for now" })).toHaveCount(
    0,
  );
  await barredFromTheApp(page);

  // The camera, which `camera=(self)` lets the page ask for (T-4.7).
  await page.getByRole("button", { name: "Open camera" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Face the camera in good light" }),
  ).toBeVisible();
  // A frame on screen before the shutter, as a person who looks at the
  // preview has: the first frame isn't drawable the instant the shutter
  // enables, and a shot taken then is black.
  await page.evaluate(
    () =>
      new Promise<void>((presented) => {
        document
          .querySelector("video")
          ?.requestVideoFrameCallback(() => presented());
      }),
  );
  await page.getByRole("button", { name: "Take selfie" }).click();

  // Checked before it's sent (T-4.7), then compared by the models on the
  // worker, woken for it (D-261), and matched: two portraits of one person.
  await expect(page.getByRole("img", { name: "Your selfie" })).toBeVisible();
  await page.getByRole("button", { name: "Use this selfie" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Comparing your selfie with your face photo" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Your selfie matched your face photo." }),
  ).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Continue" }).click();
  await inTheApp(page);
  // No PIN, so a reload restores her straight in.
  await page.reload();
  await inTheApp(page);

  // D-080: the number never went in a URL.
  expect(urls.filter((url) => url.includes(phone.slice(-8)))).toEqual([]);
});

test("J1, refused: a browser that won't say where lands on the area picker", async ({
  page,
  request,
}) => {
  // No permission granted: the browser refuses without asking.
  await signIn(page, request, freshNumber());
  await asFarAsLocation(page, ARJUN);

  await page.getByRole("button", { name: "Share my location" }).click();

  await expect(
    page.getByRole("heading", { name: "Pick your area" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Location is off for Velora in this browser" }),
  ).toBeVisible();
  // Phagwara's areas, from the API's own database (P-38).
  await expect(page.getByRole("radio")).toHaveCount(17);
  await page.getByRole("radio", { name: "Model Town" }).check();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/username$/);
});

test("J3: under 18 is refused, and the same number can't come back", async ({
  page,
  request,
}) => {
  const phone = freshNumber();
  const first = await signIn(page, request, phone);

  await page.getByLabel("Date of birth").fill("2015-06-01");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes, that's right" }).click();
  await expect(
    page.getByRole("heading", { name: "You need to be 18 to use Velora" }),
  ).toBeVisible();

  // The same number again, once the 45-second resend lock is past, as a person
  // trying later would. It is answered like any other number, and nothing is
  // sent: on Path B a ban is silence (D-072, D-073).
  await page.waitForTimeout(46_000);
  await page.goto("/login");
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(
    page.getByRole("heading", { name: "Enter the code" }),
  ).toBeVisible();
  expect(await codeFor(request, phone), "no new code reached the phone").toBe(
    first,
  );

  // The old code, all the number ever had, signs nobody in.
  await page.getByRole("textbox", { name: "Digit 1 of 6" }).fill(first);
  // By its words: Next's route announcer and the toast region are alerts too.
  await expect(
    page.getByRole("alert").filter({ hasText: "That code isn't right." }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
