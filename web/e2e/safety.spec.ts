import type { Page } from "@playwright/test";

import { expect, signUpMan, test, unlock } from "./fixtures";

/**
 * J10 (06-TESTING), T-9.1: a report with also-block, its confirmation shown,
 * and the person gone everywhere, for both of them.
 *
 * Two men sign up through the screens (`signUpMan`), each in a browser of his
 * own. A profile opens to anyone who may see it, whatever either seeks
 * (D-493), and search's `@` finds a username anywhere, so one finds the other
 * by his username, opens his profile and reports him from its ⋯ menu. After
 * it, each one's search for the other finds no one and the other's profile is
 * the one "isn't available", the same answer as an id nobody holds (D-862).
 */

/** Search for `@username`; the row it finds, if any. */
async function search(page: Page, username: string) {
  await page.goto("/discover/search");
  await unlock(page);
  await page
    .getByRole("searchbox", { name: "Search people" })
    .fill(`@${username}`);
  return page.getByRole("link", { name: new RegExp(`@${username}`) });
}

async function foundNobody(page: Page, username: string) {
  const row = await search(page, username);
  await expect(page.getByText("No one found")).toBeVisible();
  await expect(row).toHaveCount(0);
}

test("J10: a report with also-block, confirmed, and the person gone everywhere", async ({
  page,
  browser,
  request,
}) => {
  const theirs = await browser.newContext();
  const them = await theirs.newPage();
  try {
    const mine = await signUpMan(page, page.context(), request);
    const other = await signUpMan(them, theirs, request);

    const row = await search(page, other);
    await row.click();
    await expect(page).toHaveURL(/\/people\/[0-9a-f-]{36}$/);
    const profileUrl = page.url();
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("button", { name: "Report this profile" }).click();

    const sheet = page.getByRole("dialog", { name: "Report Kabir" });
    await sheet
      .getByRole("radio", { name: "Harassment or abusive messages" })
      .check();
    await expect(
      sheet.getByRole("checkbox", { name: "Also block Kabir" }),
    ).toBeChecked();
    await sheet.getByRole("button", { name: "Send report" }).click();
    await expect(sheet.getByRole("status")).toContainText("Report sent");
    await expect(sheet.getByRole("status")).toContainText(
      "They're never told who reported them",
    );
    await sheet.getByRole("button", { name: "Done" }).click();

    await expect(page.getByText("Kabir blocked")).toBeVisible();
    await expect(page).not.toHaveURL(profileUrl);

    // Gone for him: search, and the profile itself.
    await foundNobody(page, other);
    await page.goto(profileUrl);
    await unlock(page);
    await expect(page.getByText("This profile isn't available")).toBeVisible();

    // And for them, who were never told: the same nobody.
    await foundNobody(them, mine);
    await expect(them.getByText("blocked")).toHaveCount(0);
  } finally {
    await theirs.close();
  }
});
