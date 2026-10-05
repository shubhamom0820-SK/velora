import { type Page } from "@playwright/test";

import { codeFor, expect, freshNumber, signIn, test } from "./fixtures";

/**
 * J1 and J3 (06-TESTING), on Path B with the fake SMS (T-3.13). J1 ends at the
 * photos step: nobody gets further before Sprint 4 (D-068).
 *
 * J1 shares a position in Phagwara (T-4.10): the browser hands it over only
 * because the Permissions-Policy allows `geolocation=(self)`, so this is the
 * policy proved by its effect. Its twin is refused, and picks an area.
 */

const WEB = "http://127.0.0.1:3100";
// Beside Model Town, Phagwara (P-38's areas).
const PHAGWARA = { latitude: 31.2139, longitude: 75.768 };

/** Birthday to Name, as a man in Phagwara, ending on the location question. */
async function asFarAsLocation(page: Page) {
  await page.getByLabel("Date of birth").fill("2000-01-15");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "You were born on 15 January 2000.",
  );
  await page.getByRole("button", { name: "Yes, that's right" }).click();

  await expect(page).toHaveURL(/\/onboarding\/gender$/);
  await page.getByRole("radio", { name: /^Man/ }).check();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/looking-for$/);
  await page.getByRole("button", { name: "Women" }).click();
  await page.getByRole("button", { name: "Something serious" }).click();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/name$/);
  await page.getByLabel("First name").fill("Arjun");
  await page.getByLabel("Hometown, where you're from").fill("Jalandhar");
  await page.getByLabel("Where you live now").fill("Phagwara");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/location$/);
  await expect(
    page.getByRole("heading", { name: "Where are you?" }),
  ).toBeVisible();
}

test("J1: a new man signs up as far as the photos step", async ({
  page,
  context,
  request,
  urls,
}) => {
  await context.grantPermissions(["geolocation"], { origin: WEB });
  await context.setGeolocation(PHAGWARA);
  const phone = freshNumber();
  await signIn(page, request, phone);
  await asFarAsLocation(page);

  await page.getByRole("button", { name: "Share my location" }).click();

  await expect(page).toHaveURL(/\/onboarding\/username$/);
  await page.getByLabel("Username").fill(`arjun_${phone.slice(-6)}`);
  await expect(page.getByText("That one's free.")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/about$/);
  await page
    .getByLabel("About you")
    .fill(
      "Weekend trekker, filter coffee loyalist, and slow reader of novels.",
    );
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/photos$/);
  await expect(
    page.getByRole("heading", { name: "Add your photos" }),
  ).toBeVisible();
  // D-080: the number never went in a URL.
  expect(urls.filter((url) => url.includes(phone.slice(-8)))).toEqual([]);
});

test("J1, refused: a browser that won't say where lands on the area picker", async ({
  page,
  request,
}) => {
  // No permission granted: the browser refuses without asking.
  await signIn(page, request, freshNumber());
  await asFarAsLocation(page);

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
