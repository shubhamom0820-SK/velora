import AxeBuilder from "@axe-core/playwright";
import type { APIRequestContext, Page } from "@playwright/test";

import { WALKED_ROUTES, type WalkIds } from "./a11y-routes";
import { expect, signUpMan, signUpWoman, test, unlock } from "./fixtures";

/**
 * T-9.11, the accessibility pass, in a production build: a man and a woman
 * match in the deck by keyboard alone, then every signed-in screen is walked
 * as each of them (`a11y-routes.ts`, held to the page files by
 * `src/lib/a11y-routes.test.ts`), and every admin screen as staff (D-963's
 * local-only role, given to him). On each screen:
 *
 * - **axe** (WCAG 2.0 and 2.1, A and AA) finds nothing: names, labels,
 *   landmarks, ARIA, and colour contrast as the browser renders it.
 * - **the keyboard walk:** Tab from the top until focus comes round again.
 *   Every control a pointer can reach is reached, each shows a ring when it
 *   has focus (its own outline, or its wrapper's), and on an `(app)` screen
 *   the first stop is the skip link, which puts focus on `<main>`.
 *
 * Beside them, the sheets each opens (the match, the store, Filters, the
 * profile's ⋯), the PIN lock, and the deck under reduced motion: dragged, a
 * card moves and never tilts; without it, the same drag tilts it.
 *
 * Every journey's people share the run's one deck around Phagwara, so each
 * person here has a first name of their project's own and passes cards until
 * the other's is on top (as `threads.spec.ts` does). Her sign-up needs
 * Chromium's fake camera.
 */

const API = "http://127.0.0.1:8100";
const WEB = "http://127.0.0.1:3100";
// Beside Model Town, Phagwara (P-38's areas), where he picks his area.
const PHAGWARA = { latitude: 31.2139, longitude: 75.768 };
// Cards passed at most before the other's must be on top.
const DECK_LIMIT = 25;
const NAMES: Record<string, { him: string; her: string }> = {
  mobile: { him: "Vikram", her: "Ishita" },
  desktop: { him: "Kunal", her: "Tara" },
};
// WCAG 2.0 and 2.1, A and AA: what 08-DESIGN and T-9.11 ask for.
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
// Tab presses at most on one screen before the walk gives up on coming round.
const TAB_LIMIT = 250;

/** axe on the page, or on what `include` selects; nothing found. */
async function axe(page: Page, where: string, include?: string) {
  let builder = new AxeBuilder({ page }).withTags(WCAG);
  if (include) builder = builder.include(include);
  const { violations, passes } = await builder.analyze();
  // axe ran: a page with nothing checked would pass with nothing found.
  expect(passes.length, `axe checked something on ${where}`).toBeGreaterThan(5);
  console.log(`a11y: axe on ${where}: ${passes.length} rules passed`);
  expect(
    violations.map(
      (v) =>
        `${v.id} (${v.impact}): ${v.help} at ${v.nodes
          .map((node) => node.target.join(" "))
          .join(" | ")}`,
    ),
    `axe on ${where}`,
  ).toEqual([]);
}

/** Every animation that ends, ended: a sheet mid-fade isn't its own colours. */
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
}

// The API's PIN checks: 10 a minute a person (`PIN_CHECKS_PER_MINUTE`). Every
// full load locks again (T-3.10), so his walk keeps under them, one minute's
// unlocks at most 8 (his sign-up set the PIN by the same limit), rather than
// tripping the limit it doesn't test.
const PIN_CHECKS_A_MINUTE = 8;
const unlockedAt: number[] = [];

/** His PIN, at the pace the API allows. */
async function paced(page: Page) {
  const now = Date.now();
  while (unlockedAt.length > 0 && now - (unlockedAt[0] ?? 0) > 60_000) {
    unlockedAt.shift();
  }
  if (unlockedAt.length >= PIN_CHECKS_A_MINUTE) {
    await page.waitForTimeout((unlockedAt[0] ?? now) + 61_000 - now);
    unlockedAt.shift();
  }
  unlockedAt.push(Date.now());
  await unlock(page);
}

/** A full load of `path`, unlocked with his PIN when he has one. */
async function open(page: Page, path: string, pin: boolean) {
  await page.goto(path);
  if (pin) await paced(page);
  await expect(page.locator("main")).toBeVisible();
  await settled(page);
}

type Stop = {
  key: number;
  group: string | null;
  label: string;
  ringed: boolean;
};

/**
 * Focus at the very top, as on a fresh load: the next Tab goes to the first
 * stop. Nothing about it is clicked.
 */
async function focusTop(page: Page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const body = document.body;
    body.tabIndex = -1;
    body.focus();
    body.removeAttribute("tabindex");
  });
}

/**
 * The focused element, or null on the body: a key of its own, its radio group,
 * a label for a failure's message (no digits run long enough to be a number,
 * rule 15), and whether a ring shows, its own or a focus-within wrapper's.
 */
function focused(): Stop | null {
  const w = window as unknown as {
    walkKeys?: WeakMap<Element, number>;
    walkNext?: number;
  };
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) {
    return null;
  }
  w.walkKeys ??= new WeakMap();
  if (!w.walkKeys.has(el)) {
    w.walkNext = (w.walkNext ?? 0) + 1;
    w.walkKeys.set(el, w.walkNext);
  }
  const ringed = (node: Element) => {
    const style = getComputedStyle(node);
    return (
      style.outlineStyle !== "none" &&
      Number.parseFloat(style.outlineWidth) >= 2
    );
  };
  let shown = ringed(el);
  for (let node = el.parentElement; !shown && node; node = node.parentElement) {
    if (node.matches(":focus-within") && ringed(node)) shown = true;
  }
  const name = el.getAttribute("aria-label") ?? (el.textContent ?? "").trim();
  return {
    key: w.walkKeys.get(el) ?? 0,
    group:
      el instanceof HTMLInputElement && el.type === "radio" ? el.name : null,
    label: `${el.tagName.toLowerCase()} "${name.replace(/\d{6,}/g, "…").slice(0, 48)}"`,
    ringed: shown,
  };
}

/** Every control a pointer can reach on screen, keyed as `focused` keys them. */
function reachable(): Stop[] {
  const w = window as unknown as {
    walkKeys?: WeakMap<Element, number>;
    walkNext?: number;
  };
  w.walkKeys ??= new WeakMap();
  const keys = w.walkKeys;
  const selector =
    'a[href], button, input, select, textarea, summary, [tabindex], [contenteditable="true"], audio[controls], video[controls]';
  return [...document.querySelectorAll<HTMLElement>(selector)]
    .filter(
      (el) =>
        el.tabIndex >= 0 &&
        !el.matches(":disabled") &&
        !el.closest('[inert], [aria-hidden="true"]') &&
        el.checkVisibility({ visibilityProperty: true }),
    )
    .map((el) => {
      if (!keys.has(el)) {
        w.walkNext = (w.walkNext ?? 0) + 1;
        keys.set(el, w.walkNext);
      }
      const name =
        el.getAttribute("aria-label") ?? (el.textContent ?? "").trim();
      return {
        key: keys.get(el) ?? 0,
        group:
          el instanceof HTMLInputElement && el.type === "radio"
            ? el.name
            : null,
        label: `${el.tagName.toLowerCase()} "${name.replace(/\d{6,}/g, "…").slice(0, 48)}"`,
        ringed: true,
      };
    });
}

/**
 * Tab from the top until focus comes round (or leaves the page for the body):
 * every reachable control reached, each with a ring. Returns the stops.
 */
async function keyboardWalk(page: Page, where: string): Promise<Stop[]> {
  await focusTop(page);
  const stops: Stop[] = [];
  for (let presses = 0; ; presses += 1) {
    if (presses === TAB_LIMIT) {
      throw new Error(`${where}: focus never came round in ${TAB_LIMIT} Tabs`);
    }
    await page.keyboard.press("Tab");
    const stop = await page.evaluate(focused);
    if (stop === null || stop.key === stops[0]?.key) break;
    stops.push(stop);
  }
  // The walk went somewhere: every screen walked has controls.
  expect(stops.length, `${where}: Tab reached something`).toBeGreaterThan(2);
  console.log(`a11y: walk on ${where}: ${stops.length} stops`);
  const reached = new Set(stops.map((stop) => stop.key));
  const groups = new Set(stops.map((stop) => stop.group).filter(Boolean));
  const missed = (await page.evaluate(reachable)).filter(
    (control) =>
      !reached.has(control.key) &&
      !(control.group !== null && groups.has(control.group)),
  );
  expect(
    missed.map((control) => control.label),
    `${where}: every control reached by Tab`,
  ).toEqual([]);
  expect(
    stops.filter((stop) => !stop.ringed).map((stop) => stop.label),
    `${where}: a ring on every stop`,
  ).toEqual([]);
  return stops;
}

/** The skip link is the first stop, and Enter on it puts focus on `<main>`. */
async function skipsToMain(page: Page, where: string) {
  await focusTop(page);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
    `${where}: the skip link first`,
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main"), `${where}: main after it`).toBeFocused();
}

/** Like `name` from the deck by keyboard, passing every card before theirs. */
async function likeByKeyboard(page: Page, name: string) {
  const deck = page.getByRole("region", { name: "People nearby" });
  const top = deck.getByRole("article");
  for (let passed = 0; passed < DECK_LIMIT; passed += 1) {
    await expect(top).toHaveCount(1);
    const onTop = (await top.getAttribute("aria-label")) ?? "";
    if (onTop === name) {
      await page
        .getByRole("button", { name: `Like ${name}`, exact: true })
        .press("Enter");
      await expect(
        page.getByRole("status").filter({ hasText: `Liked ${name}.` }),
      ).toHaveCount(1);
      return;
    }
    await page
      .getByRole("button", { name: `Pass on ${onTop}`, exact: true })
      .press("Enter");
    await expect(
      page.getByRole("status").filter({ hasText: `Passed on ${onTop}.` }),
    ).toHaveCount(1);
    await expect(top).not.toHaveAttribute("aria-label", onTop);
  }
  throw new Error(`${name} wasn't on top after ${DECK_LIMIT} cards`);
}

/** The top card's tilt while held `dx` px across, and how far it moved. */
async function dragged(page: Page, dx: number) {
  const card = page
    .getByRole("region", { name: "People nearby" })
    .getByRole("article");
  await expect(card, "a card on top to drag").toBeVisible({ timeout: 30_000 });
  const box = await card.boundingBox();
  if (!box) throw new Error("no card on top to drag");
  const [x, y] = [box.x + box.width / 2, box.y + box.height / 2];
  await page.mouse.move(x, y);
  await page.mouse.down();
  // In steps, as a finger moves.
  await page.mouse.move(x + dx, y, { steps: 8 });
  // Its spring's transform, as react-spring writes it on the moving element.
  const read = () =>
    card.evaluate((el) => {
      for (
        let node: HTMLElement | null = el as HTMLElement;
        node;
        node = node.parentElement
      ) {
        if (node.style.transform) return node.style.transform;
      }
      return "";
    });
  await expect.poll(async () => moved(await read())).toBeGreaterThan(dx / 2);
  const transform = await read();
  // Back where it was pressed before letting go: a release of any speed
  // within 24 px decides nothing (swipeMath's flick), so the card stays.
  await page.mouse.move(x, y, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => moved(await read())).toBeLessThan(1);
  return { moved: moved(transform), tilt: tilt(transform) };
}

function moved(transform: string): number {
  return Number.parseFloat(
    /translate3d\((-?[\d.]+)px/.exec(transform)?.[1] ?? "0",
  );
}

function tilt(transform: string): number {
  return Number.parseFloat(
    /rotate\((-?[\d.]+)deg\)/.exec(transform)?.[1] ?? "0",
  );
}

/** The signed-in person's own id, from the app's own `GET /v1/me`. */
async function ownId(page: Page, pin: boolean): Promise<string> {
  const me = page.waitForResponse(
    (response) =>
      response.url() === `${API}/v1/me` &&
      response.request().method() === "GET" &&
      response.ok(),
  );
  await open(page, "/you", pin);
  return ((await (await me).json()) as { id: string }).id;
}

/** D-963's local-only role, asked from Node: the browser never calls it. */
async function makeStaff(request: APIRequestContext, userId: string) {
  const response = await request.post(`${API}/v1/test/users/${userId}/role`, {
    data: { role: "admin" },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: "admin" });
}

/** A sheet opened by keyboard: focus inside, axe clean, Escape back to its opener. */
async function sheet(
  page: Page,
  opener: string | RegExp,
  title: string,
  where: string,
) {
  const button = page.getByRole("button", { name: opener, exact: true });
  await button.press("Enter");
  const dialog = page.getByRole("dialog", { name: title });
  await expect(dialog).toBeVisible();
  await settled(page);
  expect(
    await dialog.evaluate((el) => el.contains(document.activeElement)),
    `${where}: focus inside the sheet`,
  ).toBe(true);
  await axe(page, `${where}'s sheet`, '[role="dialog"]');
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(button, `${where}: focus back on its opener`).toBeFocused();
}

test("T-9.11: every signed-in and admin screen passes axe and a keyboard-only walk, and the deck respects reduced motion", async ({
  page,
  browser,
  context,
  request,
  browserName,
}, testInfo) => {
  test.skip(
    browserName === "firefox",
    "her selfie needs Chromium's fake camera (playwright.config.ts)",
  );
  test.setTimeout(900_000);
  const names = NAMES[testInfo.project.name];
  if (!names) throw new Error(`no names for project ${testInfo.project.name}`);
  const { him: hisName, her: herName } = names;

  // Her, in the test's own browser, watched for CSP violations by the fixture.
  await context.grantPermissions(["geolocation", "camera"], { origin: WEB });
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

    await test.step("the deck under reduced motion: dragged, a card moves and never tilts", async () => {
      // Her deck loaded before he existed, as J4's does; his, fresh, has her.
      await her.goto("/discover");
      await settled(her);
      await open(him, "/discover", true);
      await him.emulateMedia({ reducedMotion: "reduce" });
      const still = await dragged(him, 80);
      expect(still.moved).toBeGreaterThan(40);
      expect(still.tilt).toBe(0);

      // The same drag without it tilts the card: the reading above is real.
      await him.emulateMedia({ reducedMotion: "no-preference" });
      const tilted = await dragged(him, 80);
      expect(tilted.moved).toBeGreaterThan(40);
      expect(tilted.tilt).toBeGreaterThan(0);
    });

    let thread = "";
    await test.step("they match in the deck by keyboard, and the match sheet passes", async () => {
      await open(her, "/discover", false);
      await likeByKeyboard(her, hisName);
      await likeByKeyboard(him, herName);

      const match = him.getByRole("dialog", {
        name: `You and ${herName} liked each other`,
      });
      await expect(match).toBeVisible();
      await settled(him);
      expect(
        await match.evaluate((el) => el.contains(document.activeElement)),
        "focus inside the match sheet",
      ).toBe(true);
      await axe(him, "the match sheet", '[role="dialog"]');
      // Tab stays inside it (Sheet's trap): a lap ends where it began.
      for (let presses = 0; presses < 6; presses += 1) {
        await him.keyboard.press("Tab");
        expect(
          await match.evaluate((el) => el.contains(document.activeElement)),
        ).toBe(true);
      }
      await match
        .getByRole("button", { name: "Open thread · 5 Velas" })
        .press("Enter");
      await expect(him).toHaveURL(/\/chats$/);
      await settled(him);
      const row = him.getByRole("link", { name: new RegExp(`^${herName}`) });
      await row.press("Enter");
      await expect(him).toHaveURL(/\/chats\/[0-9a-f-]{36}$/);
      thread = him.url().split("/").at(-1) ?? "";
    });

    const hisId = await ownId(him, true);
    const herId = await ownId(her, false);

    await test.step("the PIN lock passes axe", async () => {
      await him.goto("/you");
      await expect(
        him.getByRole("heading", { name: "Enter your PIN" }),
      ).toBeVisible();
      await settled(him);
      await axe(him, "the PIN lock");
      await paced(him);
    });

    for (const [who, person, pin, ids] of [
      ["him", him, true, { thread, other: herId, her: herId }],
      ["her", her, false, { thread, other: hisId, her: herId }],
    ] as const) {
      for (const route of WALKED_ROUTES.filter((r) =>
        r.walkers.includes(who),
      )) {
        const path = route.path(ids satisfies WalkIds);
        const where = `${route.page} as ${who}`;
        await test.step(where, async () => {
          await open(person, path, pin);
          await axe(person, where);
          await keyboardWalk(person, where);
          await skipsToMain(person, where);
        });
      }
    }

    await test.step("the sheets: his store, her Filters, his ⋯ on her profile", async () => {
      await open(him, "/wallet", true);
      // His balance, whatever the Thread left of it: the pill opens the store.
      await sheet(him, /Velas?\. Buy Velas$/, "Buy Velas", "his balance");
      await open(her, "/discover", false);
      await sheet(her, "Filters", "Filters", "her Filters");
      await open(him, `/people/${herId}`, true);
      const more = him.getByRole("button", { name: "More", exact: true });
      await more.press("Enter");
      const menu = him.getByRole("dialog");
      await expect(menu).toBeVisible();
      await settled(him);
      await axe(him, "the profile's ⋯", '[role="dialog"]');
      await him.keyboard.press("Escape");
      await expect(menu).toHaveCount(0);
      await expect(more).toBeFocused();
    });

    await makeStaff(request, hisId);
    const ids = { thread, other: herId, her: herId };
    for (const route of WALKED_ROUTES.filter((r) =>
      r.walkers.includes("staff"),
    )) {
      const where = `${route.page} as staff`;
      await test.step(where, async () => {
        await open(him, route.path(ids), true);
        await axe(him, where);
        await keyboardWalk(him, where);
      });
    }
  } finally {
    await his.close();
  }
  expect(violations, "no CSP violation on his pages").toEqual([]);
});
