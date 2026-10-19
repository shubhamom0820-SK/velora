import { readFileSync } from "node:fs";
import {
  createServer,
  request,
  type IncomingMessage,
  type Server,
  type ServerResponse,
} from "node:http";
import { loadavg } from "node:os";
import { resolve } from "node:path";

import {
  chromium,
  expect,
  test,
  type Browser,
  type BrowserContext,
} from "@playwright/test";

import type { components } from "../src/types/api";

import { API, WEB } from "./playwright.config";

/**
 * T-9.10's first load of `/discover`, and the size of the photos four screens
 * are sent: the desktop stand-in for the founder's reading on the test phone
 * (P-930). A production build in Chromium with a phone's screen (412 × 915 at
 * 2.625×, touch, as T-6.5's deck bench), its CPU slowed 4× and its network
 * shaped by DevTools' own presets, as DevTools' source defines them
 * (`front_end/core/sdk/NetworkManager.ts`, read 14 October 2026):
 *
 *   Fast 4G — 9 Mbps down, 1.5 Mbps up, 60 ms × 2.75 latency: the pass/fail
 *   Slow 4G — 1.6 Mbps down, 750 kbps up, 150 ms × 3.75 latency ("Fast 3G"
 *             before DevTools renamed it): the stress reading, recorded beside
 *
 * each throughput × 0.9 as DevTools sets it (the founder, 16 October 2026,
 * D-1030). Ten cold runs of each, interleaved, each in a fresh context.
 *
 * Every byte goes over the network, through a proxy on loopback, because
 * DevTools' throttling never touches what Playwright's `route.fulfill`
 * answers: a 247 KB photo came back in 31 ms that way at Slow 4G, against
 * 1,950 ms through a socket (seen 14 October 2026). The proxy forwards the web
 * to `next start`, answers the API as a signed-in man would see it, and the
 * public bucket with a real photo: NASA's portrait through our own re-encode,
 * 1280 × 1600 and 281 KB (`fixtures/make_photo.py`). Chrome's throttling
 * also skips CORS preflights (each OPTIONS and its GET reached the server in
 * the same millisecond), so the stand-in holds each preflight's answer for the
 * preset's latency itself, as a real round trip would cost.
 *
 * "First load" is when the top card shows its photo: the later of the largest
 * contentful paint and the moment that photo arrived, in the browser's own
 * timing. A run fails if the largest paint isn't one of the deck's photos, if
 * the top one never arrived, or if the feed was never asked for, so a page
 * that painted something else can't pass for the deck. Not the paint alone:
 * when the three photos land together (before T-9.10's fix), Chrome sometimes
 * names a card behind as the largest paint (seen 19 October 2026,
 * `bench/3.jpg`), though the top one is bigger on screen.
 *
 * Not the phone, and not production: a desktop CPU slowed by a factor; the
 * API answers at once (the real one reads a database in Mumbai); plain HTTP
 * on loopback, so no TLS handshake (one more round trip or two per origin in
 * production). Each makes the reading kinder than the street.
 */

const RUNS = 10;
const CPU = 4;
const PROXY_PORT = 8197;
const CDN = "http://127.0.0.1:9000";
const FAST_4G_BUDGET_MS = 3000;

const PRESETS = {
  fast4g: {
    latency: 60 * 2.75,
    down: ((9 * 1000 * 1000) / 8) * 0.9,
    up: ((1.5 * 1000 * 1000) / 8) * 0.9,
  },
  slow4g: {
    latency: 150 * 3.75,
    down: ((1.6 * 1000 * 1000) / 8) * 0.9,
    up: ((750 * 1000) / 8) * 0.9,
  },
} as const;
type Preset = keyof typeof PRESETS;

const PHOTO = readFileSync(resolve(__dirname, "fixtures/photo-1600.jpg"));
const PHOTO_SIDES = { width: 1280, height: 1600 };

type Schemas = components["schemas"];

const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const photoUrl = (n: number) => `${CDN}/velora-public/bench/${n}.jpg`;

const ME: Schemas["Me"] = {
  id: id(999),
  role: "user",
  status: "active",
  onboarding_step: "done",
  gender: "male",
  age: 27,
  is_verified: true,
  has_pin: false,
  referral_code: "BENCH1",
  balance: 30,
  profile: {
    first_name: "Sam",
    username: "sam",
    about: null,
    hometown: null,
    city: "Phagwara",
    seeking: "women",
    intent_ids: [1],
    interest_ids: [],
    is_hidden: false,
    hide_age: false,
    hide_distance: false,
    show_kudos: true,
    show_gifts: true,
    public_link: true,
    location: "fresh",
  },
};

function card(n: number): Schemas["Card"] {
  return {
    id: id(n),
    first_name: `Person${n}`,
    age: 22 + (n % 8),
    username: `person${n}`,
    city: "Phagwara",
    hometown: "Jalandhar",
    distance_km: 1 + (n % 9),
    intent_ids: [1, 9],
    bio_line: "Chai, cricket and long walks by the canal on Sunday evenings.",
    main_photo_url: photoUrl(n),
    shows_badge: n % 2 === 0,
    is_online: n % 3 === 0,
    is_new: n % 4 === 0,
  };
}

const CARDS = Array.from({ length: 20 }, (_, n) => card(n + 1));

const THREADS: Schemas["ThreadRowPage"] = {
  items: Array.from({ length: 12 }, (_, n) => ({
    id: id(500 + n),
    origin: "match",
    status: "active",
    expires_at: "2099-01-01T00:00:00Z",
    knotted_at: null,
    i_tied: false,
    unread: n % 2,
    last_message: {
      kind: "text",
      text: "See you at the canal?",
      mine: false,
      at: "2026-10-19T10:00:00Z",
    },
    last_message_at: "2026-10-19T10:00:00Z",
    other: {
      id: id(n + 1),
      first_name: `Person${n + 1}`,
      username: `person${n + 1}`,
      main_photo_url: photoUrl(n + 1),
      shows_badge: false,
      is_online: n % 3 === 0,
      deleted: false,
    },
  })),
  next_cursor: null,
};

const LIKES: Schemas["LikeCardPage"] = {
  items: CARDS.slice(0, 8).map((one, n) => ({
    handle: `h${n}`,
    is_super: n === 0,
    card: one,
    blurred_photo_url: null,
  })),
  next_cursor: null,
};

const PROFILE: Schemas["PublicProfile"] = {
  ...card(1),
  about: "Chai, cricket and long walks by the canal on Sunday evenings.",
  photo_urls: [1, 2, 3, 4].map(photoUrl),
  interest_ids: [],
  kudos: null,
  album_photo_count: 0,
  match_id: null,
  thread: null,
  can_gift: false,
};

const ANSWERS: Readonly<Record<string, unknown>> = {
  "/v1/auth/refresh": { access_token: "bench" },
  "/v1/me": ME,
  "/v1/prices": { super_like: 5, thread_open: 5 },
  "/v1/wallet": { balance: 30 },
  "/v1/likes/count": { count: LIKES.items.length },
  "/v1/discover": { items: CARDS, next_cursor: null, swipes_left: 50 },
  "/v1/threads": THREADS,
  "/v1/likes": LIKES,
  [`/v1/users/${id(1)}`]: PROFILE,
};

/** What one run's proxy saw. */
type Seen = {
  latency: number;
  webJsBytes: number;
  photoBytes: number;
  photos: number;
  api: string[];
  preflights: number;
};

function freshSeen(latency: number): Seen {
  return {
    latency,
    webJsBytes: 0,
    photoBytes: 0,
    photos: 0,
    api: [],
    preflights: 0,
  };
}

const cors = {
  "access-control-allow-origin": WEB,
  "access-control-allow-credentials": "true",
};

function answerApi(
  req: IncomingMessage,
  res: ServerResponse,
  url: URL,
  seen: Seen,
) {
  if (req.method === "OPTIONS") {
    seen.preflights += 1;
    // Chrome's throttling lets a preflight through untouched: a real one is
    // a round trip of its own before the request it clears.
    setTimeout(() => {
      res.writeHead(204, {
        ...cors,
        "access-control-allow-headers":
          req.headers["access-control-request-headers"] ?? "",
        "access-control-allow-methods": "GET, POST, PATCH, DELETE",
      });
      res.end();
    }, seen.latency);
    return;
  }
  seen.api.push(`${req.method} ${url.pathname}`);
  const body = ANSWERS[url.pathname];
  if (body === undefined) {
    res.writeHead(404, cors);
    res.end();
    return;
  }
  res.writeHead(200, { ...cors, "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

/** The browser's one proxy: the web forwarded, the API and the CDN answered. */
function startProxy(state: { seen: Seen }): Server {
  return createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://unknown");
    const seen = state.seen;
    if (url.host === new URL(WEB).host) {
      const upstream = request(
        {
          host: "127.0.0.1",
          port: Number(new URL(WEB).port),
          path: url.pathname + url.search,
          method: req.method,
          headers: req.headers,
        },
        (reply) => {
          res.writeHead(reply.statusCode ?? 502, reply.headers);
          const isJs = url.pathname.endsWith(".js");
          reply.on("data", (chunk: Buffer) => {
            if (isJs) seen.webJsBytes += chunk.length;
          });
          reply.pipe(res);
        },
      );
      req.pipe(upstream);
      return;
    }
    if (url.host === new URL(API).host) {
      answerApi(req, res, url, seen);
      return;
    }
    if (url.host === new URL(CDN).host) {
      seen.photos += 1;
      seen.photoBytes += PHOTO.length;
      res.writeHead(200, {
        "content-type": "image/jpeg",
        "content-length": PHOTO.length,
        "cache-control": "public, max-age=31536000, immutable",
      });
      res.end(PHOTO);
      return;
    }
    res.writeHead(502);
    res.end();
  }).listen(PROXY_PORT, "127.0.0.1");
}

async function phone(browser: Browser): Promise<BrowserContext> {
  return browser.newContext({
    viewport: { width: 412, height: 915 },
    deviceScaleFactor: 2.625,
    isMobile: true,
    hasTouch: true,
  });
}

async function shaped(context: BrowserContext, preset: Preset) {
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const net = PRESETS[preset];
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: net.latency,
    downloadThroughput: net.down,
    uploadThroughput: net.up,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU });
  return page;
}

function launch(): Promise<Browser> {
  // `<-loopback>` sends 127.0.0.1 through the proxy too, which Chromium
  // otherwise bypasses.
  return chromium.launch({
    channel: "chromium",
    proxy: { server: `http://127.0.0.1:${PROXY_PORT}`, bypass: "<-loopback>" },
  });
}

type Paint = {
  fcp: number;
  lcp: number;
  lcpOnTop: boolean;
  lcpInDeck: boolean;
  /** What the largest paint was, so a run that fails says why. */
  lcpWas: string;
  topArrived: number;
  photosAlongside: number;
};

type LoadReading = {
  preset: Preset;
  run: number;
  /** The first load: the later of the largest paint and the top photo's arrival. */
  shown_ms: number;
  fcp_ms: number;
  lcp_ms: number;
  /** Whether Chrome named the top card's photo as the largest paint. */
  lcp_on_top: boolean;
  top_arrived_ms: number;
  js_wire_kb: number;
  /** Photos started before the top card's had arrived, its own included. */
  photos_alongside_top: number;
  photos: number;
  photo_kb: number;
  preflights: number;
  load: number;
};

/** KB as the budget counts them (scripts/bundle-budget.mts): 1,000 bytes. */
const kb = (bytes: number) => Number((bytes / 1000).toFixed(1));

function range(values: readonly number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length / 2;
  const median =
    sorted.length % 2
      ? sorted[Math.floor(mid)]
      : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
  return { min: sorted[0], median, max: sorted.at(-1) };
}

test("the first load of /discover, Fast 4G and Slow 4G at 4× CPU", async () => {
  const state = { seen: freshSeen(0) };
  const proxy = startProxy(state);
  const browser = await launch();
  const readings: LoadReading[] = [];
  for (let run = 1; run <= RUNS; run += 1) {
    for (const preset of Object.keys(PRESETS) as Preset[]) {
      state.seen = freshSeen(PRESETS[preset].latency);
      const context = await phone(browser);
      const page = await shaped(context, preset);
      await page.goto(`${WEB}/discover`, { waitUntil: "commit" });
      const photo = page.getByTestId("top-card").locator("img").first();
      await expect(photo).toBeVisible({ timeout: 60_000 });
      await expect
        .poll(
          () =>
            photo.evaluate(
              (img: HTMLImageElement) => img.complete && img.naturalWidth > 0,
            ),
          { timeout: 60_000 },
        )
        .toBe(true);
      const paint = await page.evaluate(
        () =>
          new Promise<Paint>((done) => {
            new PerformanceObserver((list) => {
              const last = list.getEntries().at(-1) as
                (PerformanceEntry & { element?: Element | null }) | undefined;
              const top = document.querySelector<HTMLImageElement>(
                '[data-testid="top-card"] img',
              );
              // The deck's frame holds the top card and the two behind it.
              const deck = top?.closest(
                '[data-testid="top-card"]',
              )?.parentElement;
              const fcp = performance.getEntriesByName(
                "first-contentful-paint",
              )[0];
              // The browser's own timing: the photos it had started on before
              // the top card's had arrived, that one included.
              const photos = performance
                .getEntriesByType("resource")
                .filter((entry) => entry.name.includes("/velora-public/"));
              const topPhoto = photos.find(
                (entry) => entry.name === top?.currentSrc,
              ) as PerformanceResourceTiming | undefined;
              const element = last?.element ?? null;
              done({
                fcp: Math.round(fcp?.startTime ?? -1),
                lcp: Math.round(last?.startTime ?? -1),
                lcpOnTop: element !== null && element === top,
                lcpInDeck:
                  element instanceof HTMLImageElement &&
                  Boolean(deck?.contains(element)),
                lcpWas: element
                  ? `${element.tagName} ${
                      element instanceof HTMLImageElement
                        ? element.currentSrc
                        : (element.textContent ?? "").slice(0, 40)
                    }`
                  : "none",
                topArrived: Math.round(topPhoto?.responseEnd ?? -1),
                photosAlongside: topPhoto
                  ? photos.filter(
                      (entry) => entry.startTime < topPhoto.responseEnd,
                    ).length
                  : -1,
              });
            }).observe({ type: "largest-contentful-paint", buffered: true });
          }),
      );
      const seen = state.seen;
      await context.close();

      // The deck was what loaded: the feed asked for, a deck photo the
      // largest paint, the top card's photo arrived.
      expect(seen.api).toContain("GET /v1/discover");
      expect(paint.lcpInDeck, paint.lcpWas).toBe(true);
      expect(paint.topArrived).toBeGreaterThan(0);
      expect(paint.photosAlongside).toBeGreaterThan(0);
      const reading: LoadReading = {
        preset,
        run,
        shown_ms: Math.max(paint.lcp, paint.topArrived),
        fcp_ms: paint.fcp,
        lcp_ms: paint.lcp,
        lcp_on_top: paint.lcpOnTop,
        top_arrived_ms: paint.topArrived,
        js_wire_kb: kb(seen.webJsBytes),
        photos_alongside_top: paint.photosAlongside,
        photos: seen.photos,
        photo_kb: kb(seen.photoBytes),
        preflights: seen.preflights,
        load: Number(loadavg()[0]?.toFixed(2)),
      };
      readings.push(reading);
      console.log(JSON.stringify(reading));
    }
  }
  await browser.close();
  proxy.close();

  for (const preset of Object.keys(PRESETS) as Preset[]) {
    const mine = readings.filter((r) => r.preset === preset);
    console.log(
      JSON.stringify({
        preset,
        runs: mine.length,
        shown_ms: range(mine.map((r) => r.shown_ms)),
        lcp_ms: range(mine.map((r) => r.lcp_ms)),
        top_arrived_ms: range(mine.map((r) => r.top_arrived_ms)),
        lcp_on_top: mine.filter((r) => r.lcp_on_top).length,
        fcp_ms: range(mine.map((r) => r.fcp_ms)),
        js_wire_kb: range(mine.map((r) => r.js_wire_kb)),
        photos_alongside_top: range(mine.map((r) => r.photos_alongside_top)),
      }),
    );
  }
  // The pass/fail is Fast 4G's, every run (D-1030). Slow 4G is recorded only.
  const fast = readings
    .filter((r) => r.preset === "fast4g")
    .map((r) => r.shown_ms);
  expect(Math.max(...fast)).toBeLessThan(FAST_4G_BUDGET_MS);
});

/**
 * "Images served at the right size" (D-1030's 2× rule): a photo passes when
 * its natural width is at most twice the device pixels it fills. For
 * `object-cover`, the box is filled at the larger of its two scales, so the
 * pixels needed are the natural width times that scale times the pixel
 * ratio. Every photo on each screen is read; a screen with none fails, so a
 * page that never rendered can't pass. Unthrottled: sizes don't depend on it.
 */
test("the photos four screens are sent, against what they fill", async () => {
  const state = { seen: freshSeen(0) };
  const proxy = startProxy(state);
  const browser = await launch();
  const screens = [
    { path: "/discover", ready: '[data-testid="top-card"] img' },
    { path: "/chats", ready: "main img" },
    { path: "/discover/likes", ready: "main img" },
    { path: `/people/${id(1)}`, ready: "main img" },
  ];
  for (const screen of screens) {
    const context = await phone(browser);
    const page = await context.newPage();
    await page.goto(`${WEB}${screen.path}`);
    await expect(page.locator(screen.ready).first()).toBeVisible({
      timeout: 60_000,
    });
    await page.waitForLoadState("networkidle");
    const photos = await page.evaluate((cdn) => {
      return Array.from(document.images)
        .filter(
          (img) =>
            img.currentSrc.startsWith(cdn) &&
            img.complete &&
            img.naturalWidth > 0,
        )
        .map((img) => {
          const box = img.getBoundingClientRect();
          const scale = Math.max(
            box.width / img.naturalWidth,
            box.height / img.naturalHeight,
          );
          const needed = img.naturalWidth * scale * window.devicePixelRatio;
          return {
            natural: `${img.naturalWidth}×${img.naturalHeight}`,
            box: `${Math.round(box.width)}×${Math.round(box.height)}`,
            over: Number((img.naturalWidth / needed).toFixed(2)),
          };
        })
        .filter((photo) => photo.box !== "0×0");
    }, CDN);
    await context.close();
    expect(photos.length).toBeGreaterThan(0);
    for (const photo of photos) {
      expect(photo.natural).toBe(`${PHOTO_SIDES.width}×${PHOTO_SIDES.height}`);
    }
    const overs = photos.map((photo) => photo.over);
    console.log(
      JSON.stringify({
        screen: screen.path,
        photos: photos.length,
        boxes: [...new Set(photos.map((photo) => photo.box))],
        times_over: range(overs),
        within_2x: overs.filter((over) => over <= 2).length,
        kb_each: kb(PHOTO.length),
      }),
    );
  }
  await browser.close();
  proxy.close();
});
