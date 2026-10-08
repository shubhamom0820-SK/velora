import { readFileSync } from "node:fs";
import { loadavg } from "node:os";
import { resolve } from "node:path";

import {
  chromium,
  expect,
  test,
  type Browser,
  type Page,
} from "@playwright/test";

import { API, WEB } from "./playwright.config";

/**
 * T-6.5's "60 fps" reading, the desktop stand-in for the founder's check on
 * the test phone (the founder, 8 October 2026): a production build of the
 * deck in Chromium with a phone's screen (412 × 915 at 2.625×, touch) and its
 * CPU slowed by DevTools' own throttling, 4× (DevTools' "mid-tier mobile")
 * and 6× (its "low-end mobile"), ten runs of each, interleaved.
 *
 * Each run drags the top card 200 px right over about 0.65 s, as a thumb
 * would, and lets it fly off. requestAnimationFrame times every frame: while
 * the finger drags, each one painted and the longest gap between two; while
 * the card flies, the frames in which a spring moved it, and their rate. A run
 * whose drag didn't swipe, or whose card didn't move, fails, so an idle page's
 * 60 frames a second can't pass for the deck's. The API is answered here: a
 * signed-in man, twenty cards, each with a real 1,200-pixel photo.
 *
 * Not the phone: a desktop CPU slowed by a factor is not a phone's GPU or
 * its thermal limits, and headless Chromium paints without a display. The
 * box on T-6.5's line waits for the founder's own reading (P-500).
 */

const RUNS = 10;
const RATES = [4, 6] as const;
const PHOTO = readFileSync(
  resolve(__dirname, "../../api/tests/fixtures/faces/chari_2017.jpg"),
);

const ME = {
  id: "00000000-0000-4000-8000-0000000000aa",
  role: "user",
  status: "active",
  onboarding_step: "done",
  gender: "male",
  age: 27,
  is_verified: true,
  has_pin: false,
  referral_code: "BENCH1",
  balance: 30,
  profile: { first_name: "Sam" },
};

function cards() {
  return Array.from({ length: 20 }, (_, n) => ({
    id: `00000000-0000-4000-8000-${String(n + 1).padStart(12, "0")}`,
    first_name: `Person${n + 1}`,
    age: 22 + (n % 8),
    username: `person${n + 1}`,
    city: "Phagwara",
    hometown: "Jalandhar",
    distance_km: 1 + (n % 9),
    intent_ids: [1, 9],
    bio_line: "Chai, cricket and long walks by the canal on Sunday evenings.",
    main_photo_url: `http://127.0.0.1:9000/velora-public/bench/${n}.jpg`,
    shows_badge: n % 2 === 0,
    is_online: n % 3 === 0,
    is_new: n % 4 === 0,
  }));
}

async function answerTheApi(page: Page, swiped: string[]) {
  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    const reply = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "Access-Control-Allow-Origin": WEB },
        body: JSON.stringify(body),
      });
    if (route.request().method() === "OPTIONS") {
      return route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": WEB,
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Allow-Methods": "GET, POST",
          "Access-Control-Allow-Credentials": "true",
        },
      });
    }
    switch (url.pathname) {
      case "/v1/auth/refresh":
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: {
            "Access-Control-Allow-Origin": WEB,
            "Access-Control-Allow-Credentials": "true",
          },
          body: JSON.stringify({ access_token: "bench" }),
        });
      case "/v1/me":
        return reply(ME);
      case "/v1/prices":
        return reply({ super_like: 5, thread_open: 5 });
      case "/v1/wallet":
        return reply({ balance: 30 });
      case "/v1/discover":
        return reply({ items: cards(), next_cursor: null, swipes_left: 50 });
      case "/v1/swipes":
        swiped.push(route.request().postData() ?? "");
        return reply({ matched: false, match_id: null, swipes_left: 49 });
      default:
        return route.fulfill({ status: 404, body: "" });
    }
  });
  await page.route("http://127.0.0.1:9000/**", (route) =>
    route.fulfill({ status: 200, contentType: "image/jpeg", body: PHOTO }),
  );
}

type Reading = {
  rate: number;
  run: number;
  /** While the finger drags: every frame painted, and the longest gap. */
  drag_frames: number;
  drag_longest_ms: number;
  /** While the card flies off, a frame each spring step: their rate. */
  flight_frames: number;
  flight_fps: number;
  flight_longest_ms: number;
  /** Frames anywhere in the run that took over 25 ms (a dropped frame). */
  over_25ms: number;
  load: number;
};

type Frame = { t: number; moved: boolean };

const gapsOf = (times: number[]) =>
  times.slice(1).map((t, i) => t - (times[i] ?? t));
const round = (n: number) => Number(n.toFixed(1));

async function measure(browser: Browser, rate: number, run: number) {
  const context = await browser.newContext({
    viewport: { width: 412, height: 915 },
    deviceScaleFactor: 2.625,
    isMobile: true,
    hasTouch: true,
    baseURL: WEB,
  });
  const page = await context.newPage();
  const swiped: string[] = [];
  await answerTheApi(page, swiped);
  await page.goto("/discover");
  const card = page.getByTestId("top-card");
  await expect(card).toBeVisible();
  await page.waitForLoadState("networkidle");

  const cdp = await context.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate });

  const box = await card.boundingBox();
  if (!box) throw new Error("the top card has no box");
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 3;

  // Every frame, and whether a card's transform or opacity changed in it.
  await page.evaluate(() => {
    const frames: { t: number; moved: boolean }[] = [];
    const bench = window as unknown as { benchFrames: typeof frames };
    bench.benchFrames = frames;
    let last = "";
    const tick = (t: number) => {
      const state = Array.from(
        document.querySelectorAll<HTMLElement>(".will-change-transform"),
        (el) => `${el.style.transform}|${el.style.opacity}`,
      ).join(";");
      frames.push({ t, moved: state !== last });
      last = state;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  await page.mouse.move(x, y);
  await page.mouse.down();
  for (let step = 1; step <= 40; step += 1) {
    await page.mouse.move(x + step * 5, y + step);
    await page.waitForTimeout(16);
  }
  const released = await page.evaluate(() => performance.now());
  await page.mouse.up();
  await page.waitForTimeout(900);

  const frames = await page.evaluate(
    () => (window as unknown as { benchFrames: Frame[] }).benchFrames,
  );
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  await context.close();

  // The drag swiped: the request went, and the card flew.
  expect(swiped).toHaveLength(1);
  expect(JSON.parse(swiped[0] ?? "{}")).toMatchObject({ dir: "like" });
  const firstMove = frames.findIndex((f) => f.moved && f.t > 0);
  const drag = frames
    .slice(firstMove)
    .filter((f) => f.t <= released)
    .map((f) => f.t);
  const flight = frames
    .filter((f) => f.t > released && f.moved)
    .map((f) => f.t);
  expect(drag.length).toBeGreaterThan(20);
  expect(flight.length).toBeGreaterThan(5);
  const flightSeconds = ((flight.at(-1) ?? 0) - (flight[0] ?? 0)) / 1000;
  const all = gapsOf(frames.slice(firstMove).map((f) => f.t));

  const reading: Reading = {
    rate,
    run,
    drag_frames: drag.length,
    drag_longest_ms: round(Math.max(...gapsOf(drag))),
    flight_frames: flight.length,
    flight_fps: round((flight.length - 1) / flightSeconds),
    flight_longest_ms: round(Math.max(...gapsOf(flight))),
    over_25ms: all.filter((gap) => gap > 25).length,
    load: Number(loadavg()[0]?.toFixed(2)),
  };
  return reading;
}

test("the deck's frames while a card is dragged and flies off", async () => {
  const browser = await chromium.launch({ channel: "chromium" });
  const readings: Reading[] = [];
  for (let run = 1; run <= RUNS; run += 1) {
    for (const rate of RATES) {
      const reading = await measure(browser, rate, run);
      readings.push(reading);
      console.log(JSON.stringify(reading));
    }
  }
  await browser.close();
  const range = (values: number[]) => {
    const sorted = [...values].sort((a, b) => a - b);
    return [sorted[0], sorted.at(-1)];
  };
  for (const rate of RATES) {
    const mine = readings.filter((r) => r.rate === rate);
    console.log(
      JSON.stringify({
        rate,
        runs: mine.length,
        flight_fps_range: range(mine.map((r) => r.flight_fps)),
        flight_longest_ms_range: range(mine.map((r) => r.flight_longest_ms)),
        drag_longest_ms_range: range(mine.map((r) => r.drag_longest_ms)),
        frames_over_25ms_total: mine.reduce((n, r) => n + r.over_25ms, 0),
        frames_total: mine.reduce(
          (n, r) => n + r.drag_frames + r.flight_frames,
          0,
        ),
      }),
    );
  }
});
