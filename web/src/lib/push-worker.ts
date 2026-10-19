import { APP_NAME } from "./app";
import { FALLBACK_ROUTE, ROUTES, TAGS, sentences } from "./notification-view";
import { offlinePage } from "./offline-page";

/**
 * The service worker's source (T-9.4, D-859), served at `/sw.js` by its route
 * handler: no library, no build step of its own. It is the site's only worker,
 * the PWA's too (T-9.7). It does three things:
 *
 * - **push**: the payload is a kind and ids, never words; the words are
 *   `en.ts`'s, put here as data at build time, so the worker and the in-app
 *   list say the same thing (`push-worker.test.ts` holds them equal). A name
 *   comes only when the person hasn't turned on "Hide names".
 * - **notificationclick**: focuses a tab of this site on the notification's
 *   route, or opens one. The route is built from the tables below, a path on
 *   this site only, whatever the payload says.
 * - **fetch** (T-9.7, D-1040): a page load on this site goes to the network,
 *   through navigation preload, and only when the network fails does the
 *   worker answer, with the offline page (`offline-page.ts`) it carries.
 *   Nothing is cached, ever: no stale page, and no one's page shown to anyone
 *   else. Every other request is left to the browser.
 *
 * `tokensCss` is `tokens.css`, which the offline page is drawn with.
 */
export function serviceWorkerSource(tokensCss: string): string {
  const tables = {
    app: APP_NAME,
    sentences: sentences(),
    routes: ROUTES,
    tags: TAGS,
    fallback: FALLBACK_ROUTE,
  };
  return `"use strict";
// ${APP_NAME}'s service worker (T-9.4). Generated from web/src/lib/push-worker.ts.
const TABLES = ${JSON.stringify(tables)};
const OFFLINE = ${JSON.stringify(offlinePage(tokensCss))};

function variantOf(kind, data) {
  if (kind === "like" && data.super === true) return "superLike";
  if (kind === "album_decided" && data.granted === true) return "albumGranted";
  const variants = {
    match: "match", thread: "thread", message: "message", like: "like",
    gift: "gift", album_request: "albumRequest", album_decided: "albumDeclined",
    knot_requested: "knotRequested", knot_accepted: "knotAccepted",
    thread_expiring: "threadExpiring", low_balance: "lowBalance",
  };
  return Object.prototype.hasOwnProperty.call(variants, kind) ? variants[kind] : "other";
}

function fill(template, data) {
  let missing = false;
  const filled = template.replace(/\\{(\\w+)\\}/g, (_, field) => {
    const value = data[field];
    if (typeof value !== "string" || value === "") {
      missing = true;
      return "";
    }
    return encodeURIComponent(value);
  });
  return missing ? null : filled;
}

function own(table, key) {
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key] : undefined;
}

function viewOf(data) {
  const kind = typeof data.kind === "string" ? data.kind : "";
  const words = TABLES.sentences[variantOf(kind, data)];
  const name = typeof data.name === "string" && data.name !== "" ? data.name : null;
  const body = name ? words.named.split("{name}").join(name) : words.plain;
  const route = own(TABLES.routes, kind);
  const tag = own(TABLES.tags, kind);
  return {
    title: TABLES.app,
    body,
    tag: (tag && fill(tag, data)) || kind || "other",
    url: (route && fill(route, data)) || TABLES.fallback,
  };
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    const parsed = event.data ? event.data.json() : {};
    if (parsed && typeof parsed === "object") data = parsed;
  } catch (_) {
    data = {};
  }
  const view = viewOf(data);
  event.waitUntil(
    self.registration.showNotification(view.title, {
      body: view.body,
      tag: view.tag,
      renotify: false,
      data: { url: view.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const path = (event.notification.data && event.notification.data.url) || TABLES.fallback;
  const url = new URL(path, self.location.origin);
  const target = url.origin === self.location.origin ? url.href : new URL(TABLES.fallback, self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (new URL(client.url).origin === self.location.origin && "focus" in client) {
          return client.navigate(target).then((navigated) => (navigated || client).focus());
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});

function offlineResponse() {
  return new Response(OFFLINE.html, {
    status: 503,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": OFFLINE.csp,
      "Cache-Control": "no-store",
    },
  });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.mode !== "navigate" || request.method !== "GET") return;
  if (new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(
    (async () => {
      try {
        const preloaded = await event.preloadResponse;
        if (preloaded) return preloaded;
        return await self.fetch(request);
      } catch (_) {
        return offlineResponse();
      }
    })(),
  );
});

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  const preload = self.registration.navigationPreload;
  event.waitUntil(
    Promise.all([self.clients.claim(), preload ? preload.enable() : Promise.resolve()]),
  );
});
`;
}
