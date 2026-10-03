import { codeFor, expect, freshNumber, signIn, test } from "./fixtures";

/**
 * J1 and J3 (06-TESTING), on Path B with the fake SMS (T-3.13). J1 ends at the
 * photos step: nobody gets further before Sprint 4 (D-068).
 */

test("J1: a new man signs up as far as the photos step", async ({
  page,
  request,
  urls,
}) => {
  const phone = freshNumber();
  await signIn(page, request, phone);

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
