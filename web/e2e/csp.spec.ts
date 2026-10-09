import { expect, type Page, test } from "@playwright/test";

/**
 * D-541 (T-6.6): the sign-in and app routes are served with a nonce per
 * response in place of 'unsafe-inline', proved by what the browser refuses,
 * never only by the header being there. The static pages keep the static
 * policy, and stay static.
 *
 * Plain `@playwright/test`, not ./fixtures: these cases cause a violation on
 * purpose, which the fixtures' watch would fail.
 */

/** Someone else's markup, as an XSS would put it on the page. */
async function inject(page: Page) {
  await page.evaluate(() => {
    (window as unknown as { __ran: boolean }).__ran = false;
    const host = document.createElement("div");
    host.innerHTML = '<img src="/nowhere.png" onerror="window.__ran = true">';
    document.body.append(host);
  });
}

function ran(page: Page) {
  return page.evaluate(() => (window as unknown as { __ran: boolean }).__ran);
}

test("a nonce route sends a fresh nonce, no 'unsafe-inline', and still runs Next", async ({
  page,
}) => {
  const first = await page.goto("/login");
  const policy = first?.headers()["content-security-policy"] ?? "";
  expect(policy).toMatch(
    /script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/,
  );
  expect(policy).not.toContain("'unsafe-inline'");
  // Next hydrated: the form answers a person.
  await page.getByLabel("Mobile number").fill("9800000000");
  await expect(page.getByLabel("Mobile number")).toHaveValue("9800000000");

  const second = await page.goto("/login");
  expect(second?.headers()["content-security-policy"]).not.toBe(policy);
});

test("an injected inline handler runs on a static page and is refused on a nonce route", async ({
  page,
}) => {
  const violations: string[] = [];
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP-VIOLATION ${event.violatedDirective}`);
    });
  });
  page.on("console", (message) => {
    if (message.text().startsWith("CSP-VIOLATION"))
      violations.push(message.text());
  });

  // The static policy allows inline handlers: the check below can see one run.
  const home = await page.goto("/");
  expect(home?.headers()["content-security-policy"]).toContain(
    "'unsafe-inline'",
  );
  await inject(page);
  await expect.poll(() => ran(page)).toBe(true);
  expect(violations).toEqual([]);

  // Polled, never a fixed wait: the browser reports a violation when it gets
  // to it (CI's runner took longer than 500 ms, 8 October 2026).
  await page.goto("/login");
  await inject(page);
  await expect
    .poll(() =>
      violations.some((v) => v.startsWith("CSP-VIOLATION script-src")),
    )
    .toBe(true);
  expect(await ran(page)).toBe(false);
});

/**
 * T-7.12 (D-059): the app's socket, allowed to the API's own host on the nonce
 * routes, where the app lives, and nowhere else. Proved by what the browser
 * refuses: a socket to another host on an app route, and the API's own on a
 * static page, whose policy names the API's http origin and no socket.
 */
const API_SOCKET = "ws://127.0.0.1:8100/ws";
const ANOTHER_SOCKET = "ws://127.0.0.1:8101/ws";

async function watchSockets(page: Page): Promise<string[]> {
  const refused: string[] = [];
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(
        `CSP-VIOLATION ${event.effectiveDirective} ${event.blockedURI}`,
      );
    });
  });
  page.on("console", (message) => {
    if (message.text().startsWith("CSP-VIOLATION connect-src"))
      refused.push(message.text());
  });
  return refused;
}

/** Opens a socket from the page; how it ended, once it has. */
function openSocket(page: Page, url: string) {
  return page.evaluate(
    (target) =>
      new Promise<string>((resolve) => {
        try {
          const socket = new WebSocket(target);
          socket.onopen = () => {
            socket.close();
            resolve("open");
          };
          socket.onerror = () => resolve("error");
          socket.onclose = (event) => resolve(`closed ${event.code}`);
        } catch (error) {
          resolve(`threw ${(error as Error).name}`);
        }
      }),
    url,
  );
}

test("an app route lets the socket reach the API's own host and no other", async ({
  page,
}) => {
  const refused = await watchSockets(page);
  const response = await page.goto("/login");

  // No ticket, so the API refuses it (4401); the browser never did.
  await openSocket(page, API_SOCKET);
  await openSocket(page, ANOTHER_SOCKET);

  // The browser's own verdict first: another host refused, ours never.
  await expect
    .poll(() => refused.some((v) => v.includes("127.0.0.1:8101")))
    .toBe(true);
  expect(refused.filter((v) => v.includes("127.0.0.1:8100"))).toEqual([]);
  expect(response?.headers()["content-security-policy"]).toContain(
    "connect-src 'self' http://127.0.0.1:8100 ws://127.0.0.1:8100",
  );
});

test("a static page refuses the API's socket: its policy names no socket", async ({
  page,
}) => {
  const refused = await watchSockets(page);
  const response = await page.goto("/");
  expect(response?.headers()["content-security-policy"]).not.toMatch(/ws:/);

  await openSocket(page, API_SOCKET);

  await expect
    .poll(() => refused.some((v) => v.includes("127.0.0.1:8100")))
    .toBe(true);
});
