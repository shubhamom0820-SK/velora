import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { APP_NAME } from "./app";
import {
  FALLBACK_ROUTE,
  type NotificationData,
  routeFor,
  sentenceFor,
  tagFor,
} from "./notification-view";
import { serviceWorkerSource } from "./push-worker";

type Shown = {
  title: string;
  options: NotificationOptions & { renotify?: boolean };
};
type Listener = (event: unknown) => void;

/**
 * The worker's source run as a browser would run it, against a stand-in
 * `self`: what `push` shows, and where `notificationclick` goes.
 */
function boot(origin = "https://app.test") {
  const listeners: Record<string, Listener> = {};
  const shown: Shown[] = [];
  const opened: string[] = [];
  const navigated: string[] = [];
  let windows: {
    url: string;
    navigate: (url: string) => Promise<unknown>;
    focus: () => Promise<unknown>;
  }[] = [];
  const self = {
    location: { origin },
    addEventListener: (type: string, listener: Listener) => {
      listeners[type] = listener;
    },
    registration: {
      showNotification: (title: string, options: Shown["options"]) => {
        shown.push({ title, options });
        return Promise.resolve();
      },
    },
    clients: {
      matchAll: () => Promise.resolve(windows),
      openWindow: (url: string) => {
        opened.push(url);
        return Promise.resolve(null);
      },
      claim: () => Promise.resolve(),
    },
    skipWaiting: () => Promise.resolve(),
  };
  new Function("self", serviceWorkerSource())(self);

  function fire(type: string, event: unknown): void {
    const listener = listeners[type];
    if (!listener) throw new Error(`the worker has no ${type} listener`);
    listener(event);
  }

  async function push(payload: unknown): Promise<Shown> {
    let waited: Promise<unknown> = Promise.resolve();
    fire("push", {
      data:
        payload === undefined
          ? null
          : {
              json: () => {
                if (typeof payload === "string") return JSON.parse(payload);
                return payload;
              },
            },
      waitUntil: (promise: Promise<unknown>) => {
        waited = promise;
      },
    });
    await waited;
    const last = shown.at(-1);
    if (!last) throw new Error("nothing shown");
    return last;
  }

  async function click(url: string | undefined): Promise<void> {
    let waited: Promise<unknown> = Promise.resolve();
    fire("notificationclick", {
      notification: {
        data: url === undefined ? undefined : { url },
        close: vi.fn(),
      },
      waitUntil: (promise: Promise<unknown>) => {
        waited = promise;
      },
    });
    await waited;
  }

  return {
    push,
    click,
    opened,
    navigated,
    setWindows: (urls: string[]) => {
      windows = urls.map((url) => ({
        url,
        navigate: (to: string) => {
          navigated.push(to);
          return Promise.resolve(null);
        },
        focus: () => Promise.resolve(null),
      }));
    },
  };
}

const ID = "6f1c2a40-8d1e-4a7b-9c4e-0a2b3c4d5e6f";
const THREAD = "9a8b7c6d-1111-4222-8333-444455556666";

const CASES: [string, NotificationData][] = [
  ["match", { user_id: ID }],
  ["thread", { thread_id: THREAD, user_id: ID }],
  ["message", { thread_id: THREAD, user_id: ID }],
  ["like", { user_id: ID, super: false }],
  ["like", { user_id: ID, super: true }],
  ["like", { super: true }],
  ["gift", { user_id: ID }],
  ["album_request", { user_id: ID }],
  ["album_decided", { user_id: ID, granted: true }],
  ["album_decided", { user_id: ID, granted: false }],
  ["knot_requested", { thread_id: THREAD, user_id: ID }],
  ["knot_accepted", { thread_id: THREAD, user_id: ID }],
  ["thread_expiring", { thread_id: THREAD }],
  ["low_balance", {}],
  ["something_new", {}],
];

describe("the service worker (T-9.4)", () => {
  it.each(CASES)(
    "shows %s %j as the in-app list says it, with a name and without",
    async (kind, data) => {
      const worker = boot();
      for (const name of ["Arjun", undefined]) {
        const shown = await worker.push({ kind, ...data, name });
        expect(shown.title).toBe(APP_NAME);
        expect(shown.options.body).toBe(sentenceFor(kind, data, name));
        expect(shown.options.tag).toBe(tagFor(kind, data));
        expect(shown.options.data).toEqual({ url: routeFor(kind, data) });
        expect(shown.options.renotify).toBe(false);
      }
    },
  );

  it("names nobody when the push carries no name (Hide names, D-542)", async () => {
    const shown = await boot().push({
      kind: "message",
      thread_id: THREAD,
      user_id: ID,
    });
    expect(shown.options.body).toBe(t("notifications.kinds.message.plain"));
  });

  it("shows something generic for a payload it can't read", async () => {
    const worker = boot();
    for (const payload of [undefined, "not json", 42, null]) {
      const shown = await worker.push(payload);
      expect(shown.options.body).toBe(
        t("notifications.kinds.other.plain", { app: APP_NAME }),
      );
      expect(shown.options.data).toEqual({ url: FALLBACK_ROUTE });
    }
  });

  it.each([
    "thread",
    "message",
    "knot_requested",
    "knot_accepted",
    "thread_expiring",
  ])("opens the conversation for %s (P-752)", async (kind) => {
    const shown = await boot().push({ kind, thread_id: THREAD, user_id: ID });
    expect(shown.options.data).toEqual({ url: `/chats/${THREAD}` });
  });

  it("opens the sender's profile for a gift (T-8.10)", async () => {
    const shown = await boot().push({ kind: "gift", user_id: ID });
    expect(shown.options.data).toEqual({ url: `/people/${ID}` });
  });

  it("keeps ids inside their path segment", async () => {
    const shown = await boot().push({
      kind: "match",
      user_id: "../../wallet?x=1",
    });
    expect(shown.options.data).toEqual({
      url: "/people/..%2F..%2Fwallet%3Fx%3D1",
    });
  });

  it("opens the route in a new window when none of the site's is open", async () => {
    const worker = boot();
    worker.setWindows(["https://elsewhere.test/"]);
    await worker.click("/wallet");
    expect(worker.opened).toEqual(["https://app.test/wallet"]);
  });

  it("brings the site's open window to the route", async () => {
    const worker = boot();
    worker.setWindows(["https://app.test/discover"]);
    await worker.click("/chats");
    expect(worker.navigated).toEqual(["https://app.test/chats"]);
    expect(worker.opened).toEqual([]);
  });

  it("never leaves the site, whatever a notification's data says", async () => {
    const worker = boot();
    worker.setWindows([]);
    await worker.click("https://evil.test/phish");
    await worker.click("//evil.test/phish");
    await worker.click(undefined);
    expect(worker.opened).toEqual([
      `https://app.test${FALLBACK_ROUTE}`,
      `https://app.test${FALLBACK_ROUTE}`,
      `https://app.test${FALLBACK_ROUTE}`,
    ]);
  });

  it("carries no word of an hour to her: the kind reaches only him (P-460)", () => {
    // The API never sends `thread_expiring` to a woman (D-554, its test); the
    // worker's words for it name no time, no price.
    const words = t("notifications.kinds.threadExpiring.plain");
    expect(words).not.toMatch(/\d|minute|hour|Vela/i);
  });
});
