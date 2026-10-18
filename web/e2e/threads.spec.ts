import type { APIRequestContext, Page } from "@playwright/test";

import { expect, signUpMan, signUpWoman, test, unlock } from "./fixtures";

/**
 * J4 to J7 (06-TESTING), T-7.13: a man and a woman, each in a browser of
 * their own, match in the deck; he opens the Thread (−5) and they write both
 * ways live; she sends a voice note, he unlocks it (−5) and plays it; the
 * hour runs out, his side goes read-only and her message still reaches him,
 * and he re-opens it (−2); then both tie the knot and it is a Knot, with no
 * countdown. One journey, a step for each: each needs the last one's state.
 *
 * J7 comes before J6: a Knot never expires (D-003). The hour is run out by
 * the API's local-only `POST /v1/test/threads/{id}/expire` (D-930), which
 * ends the hour at the moment it is asked, so the API, the worker's sweep and
 * the browser each see it run out by their own clock, and her voice note,
 * sent under a second before, is still inside it; no clock is moved. He then
 * loads the screen again, whatever the sweep has done by then.
 *
 * His Velas: 5 on sign-up (D-470), all of them on the Thread (D-098), so his
 * first tap on Unlock is `INSUFFICIENT_CREDITS` and opens the store, where he
 * buys 30 on the fake gateway (36 with the first purchase's bonus), as J8.
 * 5 → 0 → 36 → 31 → 29, and the knot is free.
 *
 * Every journey's people share the run's database and its one deck around
 * Phagwara, so each person here has a first name of their project's own and
 * passes cards until the other's is on top. Her sign-up needs Chromium's fake
 * camera; her voice note, its fake microphone.
 */

const API = "http://127.0.0.1:8100";
const WEB = "http://127.0.0.1:3100";
// Beside Model Town, Phagwara (P-38's areas), where he picks his area.
const PHAGWARA = { latitude: 31.2139, longitude: 75.768 };
// Cards passed at most before the other's must be on top: every journey of a
// run signs up fewer people than this into Phagwara.
const DECK_LIMIT = 25;
// The deck's own names never repeat across the two projects (`playwright.config.ts`).
const NAMES: Record<string, { him: string; her: string }> = {
  mobile: { him: "Arjun", her: "Meera" },
  desktop: { him: "Rohan", her: "Anika" },
};
// A Thread's countdown, as `Countdown` draws it: never on her side (D-554).
const COUNTDOWN = /\d+[mh] left|Ran out/;

/** His balance, as the header's pill says it. */
async function pillSays(page: Page, velas: number) {
  await expect(
    page.getByRole("button", {
      name: `${velas} ${velas === 1 ? "Vela" : "Velas"}. Buy Velas`,
    }),
  ).toBeVisible();
}

/** Like `name` from the deck, passing every card before theirs. */
async function likeInDeck(page: Page, name: string) {
  const deck = page.getByRole("region", { name: "People nearby" });
  const top = deck.getByRole("article");
  for (let passed = 0; passed < DECK_LIMIT; passed += 1) {
    await expect(top).toHaveCount(1);
    const onTop = await top.getAttribute("aria-label");
    if (onTop === name) {
      // The buttons name who is on top (T-9.11).
      await page
        .getByRole("button", { name: `Like ${name}`, exact: true })
        .click();
      return;
    }
    await page
      .getByRole("button", { name: `Pass on ${onTop}`, exact: true })
      .click();
    await expect(top).not.toHaveAttribute("aria-label", onTop ?? "");
  }
  throw new Error(`${name} wasn't on top after ${DECK_LIMIT} cards`);
}

/** The chat with `name`, opened from the chats list. */
async function openChat(page: Page, name: string): Promise<string> {
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Chats" })
    .click();
  await expect(page).toHaveURL(/\/chats$/);
  await page.getByRole("link", { name: new RegExp(`^${name}`) }).click();
  await expect(page).toHaveURL(/\/chats\/[0-9a-f-]{36}$/);
  return page.url().split("/").at(-1) ?? "";
}

/** A message sent from the composer. */
async function write(page: Page, body: string) {
  await page.getByRole("textbox", { name: "Message" }).fill(body);
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

/** The message on screen, arrived by the socket: the page never reloaded. */
async function arrives(page: Page, body: string) {
  await expect(page.getByText(body, { exact: true })).toBeVisible();
}

/** The fake gateway's webhook for the payment, as Razorpay would send it. */
async function captured(request: APIRequestContext, paymentId: string) {
  const response = await request.post(`${API}/v1/test/payments/webhook`, {
    data: { payment_id: paymentId, outcome: "captured" },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ delivered_status: 200 });
}

/** Her side says nothing of the hour or of Velas (D-097, D-554). */
async function saysNothingOfTime(page: Page) {
  const main = page.locator("main");
  await expect(main).not.toContainText(COUNTDOWN);
  await expect(main).not.toContainText(/Vela/);
  await expect(page.getByRole("region", { name: /hour/ })).toHaveCount(0);
}

test("J4–J7: a match opened, chat live both ways, a voice note unlocked, the hour run out and re-opened, the knot tied", async ({
  page,
  browser,
  context,
  request,
  browserName,
}, testInfo) => {
  test.skip(
    browserName === "firefox",
    "her selfie and her voice note need Chromium's fake devices (playwright.config.ts)",
  );
  const names = NAMES[testInfo.project.name];
  if (!names) throw new Error(`no names for project ${testInfo.project.name}`);
  const { him: hisName, her: herName } = names;

  // Her, in the test's own browser, watched for CSP violations by the fixture.
  await context.grantPermissions(["geolocation", "camera", "microphone"], {
    origin: WEB,
  });
  await context.setGeolocation(PHAGWARA);
  const her = page;
  await signUpWoman(her, request, herName);

  // Him, in a browser of his own, watched the same way here.
  const his = await browser.newContext({ baseURL: WEB });
  const violations: string[] = [];
  try {
    const him = await his.newPage();
    him.on("console", (message) => {
      if (message.text().includes("Content Security Policy")) {
        violations.push(message.text());
      }
    });
    await signUpMan(him, his, request, hisName);
    await pillSays(him, 5);

    let threadId = "";

    await test.step("J4: they match in the deck, he opens the Thread (−5), and they write both ways live", async () => {
      // Her deck loaded before he existed: a fresh look finds him.
      await her.goto("/discover");
      await likeInDeck(her, hisName);
      await likeInDeck(him, herName);

      const match = him.getByRole("dialog", {
        name: `You and ${herName} liked each other`,
      });
      await expect(match).toBeVisible();
      await match
        .getByRole("button", { name: "Open thread · 5 Velas" })
        .click();
      // The sheet goes to the chats list, not the Thread (P-770).
      await expect(him).toHaveURL(/\/chats$/);
      await pillSays(him, 0);
      threadId = await openChat(him, herName);
      await expect(
        him.getByRole("heading", { name: "Say hello" }),
      ).toBeVisible();

      await openChat(her, hisName);
      await saysNothingOfTime(her);

      await write(him, `Hello ${herName}, how was your day?`);
      await arrives(her, `Hello ${herName}, how was your day?`);
      await write(her, "Long, but good. Yours?");
      await arrives(him, "Long, but good. Yours?");
      // He opened it and writes free while it is live (D-551).
      await pillSays(him, 0);
      await saysNothingOfTime(her);
    });

    await test.step("J5: her voice note, unlocked by him (−5) once he has bought Velas, and played", async () => {
      await her.getByRole("button", { name: "Record a voice note" }).click();
      await expect(her.getByText(/^Recording, 0:0[2-9]$/)).toBeVisible();
      await her.getByRole("button", { name: "Stop recording" }).click();
      await expect(
        her.getByRole("button", { name: "Send the voice note" }),
      ).toBeVisible();
      await her.getByRole("button", { name: "Send the voice note" }).click();
      await expect(
        her.getByRole("group", { name: /^Voice note, 0:0\d$/ }),
      ).toBeVisible({ timeout: 30_000 });
      await saysNothingOfTime(her);

      const note = him.getByRole("group", { name: /^Voice note, 0:0\d$/ });
      const unlockIt = note.getByRole("button", {
        name: "Unlock this voice note for 5 Velas",
      });
      await expect(unlockIt).toBeVisible();

      // Out of Velas: the refusal opens the store (QueryProvider), J8's way.
      await unlockIt.click();
      const store = him.getByRole("dialog", { name: "Buy Velas" });
      await expect(store).toBeVisible();
      const ordered = him.waitForResponse(
        (response) =>
          response.url() === `${API}/v1/payments/orders` &&
          response.request().method() === "POST",
      );
      await store.getByRole("button", { name: /^30 Velas/ }).click();
      const order = await ordered;
      expect(order.status()).toBe(200);
      const { payment_id: paymentId } = (await order.json()) as {
        payment_id: string;
      };
      await captured(request, paymentId);
      await him
        .getByRole("dialog", { name: "Test checkout" })
        .getByRole("button", { name: "Payment went through" })
        .click();
      await expect(
        him
          .getByRole("status")
          .filter({ hasText: "36 Velas added to your balance" }),
      ).toBeVisible();
      await expect(him.getByRole("dialog")).toHaveCount(0);
      await pillSays(him, 36);

      await unlockIt.click();
      await pillSays(him, 31);
      const play = note.getByRole("button", { name: "Play the voice note" });
      await expect(play).toBeVisible();
      await play.click();
      await expect(
        note.getByRole("button", { name: "Pause the voice note" }),
      ).toBeVisible();
      // Playing: its position moves, from the bytes the storage served him.
      await expect
        .poll(() =>
          note
            .locator("audio")
            .evaluate((audio: HTMLAudioElement) => audio.currentTime),
        )
        .toBeGreaterThan(0);
    });

    await test.step("J7: the hour runs out, his side is read-only, hers still reaches him, and he re-opens it (−2)", async () => {
      const expired = await request.post(
        `${API}/v1/test/threads/${threadId}/expire`,
      );
      expect(expired.status()).toBe(200);

      await him.reload();
      await unlock(him);
      const panel = him.getByRole("region", { name: "The hour ran out." });
      await expect(panel).toBeVisible();
      // Read-only: no composer, and the history all there (D-097).
      await expect(him.getByRole("textbox", { name: "Message" })).toHaveCount(
        0,
      );
      await expect(him.getByText("Long, but good. Yours?")).toBeVisible();

      // Hers goes through, and her side shows nothing of it (D-097).
      await saysNothingOfTime(her);
      await write(her, "Did you fall asleep?");
      await arrives(her, "Did you fall asleep?");
      await saysNothingOfTime(her);
      await arrives(him, "Did you fall asleep?");
      await expect(
        him.getByRole("region", {
          name: "She wrote back. The hour had run out.",
        }),
      ).toBeVisible();

      await him.getByRole("button", { name: "Re-open · 2 Velas" }).click();
      await expect(
        him.getByRole("region", { name: /hour had run out|hour ran out/ }),
      ).toHaveCount(0);
      await pillSays(him, 29);
      await write(him, "Not asleep, just slow. Sorry!");
      await arrives(her, "Not asleep, just slow. Sorry!");
    });

    await test.step("J6: both tie the knot, it is a Knot, and the Knots tab has it with no countdown", async () => {
      await him.getByRole("button", { name: "Tie the knot" }).click();
      await expect(
        him.getByText(`You tied it. Waiting for ${herName}.`),
      ).toBeVisible();
      await her.getByRole("button", { name: "Tie the knot" }).click();

      for (const [who, other] of [
        [her, hisName],
        [him, herName],
      ] as const) {
        const tied = who.getByRole("dialog", {
          name: `You and ${other} tied the knot`,
        });
        await expect(tied).toBeVisible();
        await tied.getByRole("button", { name: "Keep talking" }).click();
        await expect(tied).toHaveCount(0);
      }
      await expect(him.locator("main")).not.toContainText(COUNTDOWN);
      // Free: the knot moved nothing (D-003).
      await pillSays(him, 29);

      await him
        .getByRole("navigation", { name: "Main" })
        .getByRole("link", { name: "Chats" })
        .click();
      await expect(him).toHaveURL(/\/chats$/);
      await him.getByRole("button", { name: /^Knots/ }).click();
      const row = him.getByRole("link", { name: new RegExp(`^${herName}`) });
      await expect(row).toBeVisible();
      await expect(row).not.toContainText(COUNTDOWN);
    });
  } finally {
    await his.close();
  }
  expect(violations, "no CSP violation on his pages").toEqual([]);
});
