import { t } from "@/i18n/t";

import { APP_NAME } from "./app";

/**
 * What a notification says and where it leads (T-9.4), from what the API
 * sends: a kind and ids, never words (D-033). The in-app list reads these
 * functions; the service worker (`/sw.js`) gets the same tables as data and a
 * copy of `variantOf` and `fill`, which a test holds equal to these, kind by
 * kind (`push-worker.test.ts`).
 *
 * Every route is a path on this site, its ids filled in encoded: a payload can
 * name a person or a Thread, never a place.
 */

export type NotificationData = { readonly [key: string]: unknown };

/** The sentence each kind (and each of its two variants) has, in `en.ts`. */
export const VARIANTS = [
  "match",
  "thread",
  "message",
  "like",
  "superLike",
  "gift",
  "albumRequest",
  "albumGranted",
  "albumDeclined",
  "knotRequested",
  "knotAccepted",
  "threadExpiring",
  "lowBalance",
  "other",
] as const;
export type Variant = (typeof VARIANTS)[number];

const VARIANT_OF_KIND: Readonly<Record<string, Variant>> = {
  match: "match",
  thread: "thread",
  message: "message",
  like: "like",
  gift: "gift",
  album_request: "albumRequest",
  album_decided: "albumDeclined",
  knot_requested: "knotRequested",
  knot_accepted: "knotAccepted",
  thread_expiring: "threadExpiring",
  low_balance: "lowBalance",
};

/**
 * Where each kind leads. A Thread's kinds open its conversation (T-7.11's
 * `/chats/[id]`, P-752); a gift opens You,
 * where her received gifts are (T-8.10), and an album request her album's
 * requests (T-8.8).
 */
export const ROUTES: Readonly<Record<string, string>> = {
  match: "/people/{user_id}",
  thread: "/chats/{thread_id}",
  message: "/chats/{thread_id}",
  like: "/discover/likes",
  gift: "/you",
  album_request: "/you/album-requests",
  album_decided: "/people/{user_id}",
  knot_requested: "/chats/{thread_id}",
  knot_accepted: "/chats/{thread_id}",
  thread_expiring: "/chats/{thread_id}",
  low_balance: "/wallet",
};
export const FALLBACK_ROUTE = "/notifications";

/**
 * A push's tag: a newer one with the same tag replaces the one shown, quietly
 * (`renotify: false`), so a hundred likes are one notification on the phone,
 * and a Thread's messages one per Thread.
 */
export const TAGS: Readonly<Record<string, string>> = {
  match: "match:{user_id}",
  thread: "thread:{thread_id}",
  message: "thread:{thread_id}",
  like: "likes",
  knot_requested: "thread:{thread_id}",
  knot_accepted: "thread:{thread_id}",
  thread_expiring: "thread:{thread_id}",
};

export function variantOf(kind: string, data: NotificationData): Variant {
  if (kind === "like" && data.super === true) return "superLike";
  if (kind === "album_decided" && data.granted === true) return "albumGranted";
  return VARIANT_OF_KIND[kind] ?? "other";
}

/** `template` with each `{field}` from `data`, encoded; null if one is missing. */
export function fill(template: string, data: NotificationData): string | null {
  let missing = false;
  const filled = template.replace(/\{(\w+)\}/g, (_, field: string) => {
    const value = data[field];
    if (typeof value !== "string" || value === "") {
      missing = true;
      return "";
    }
    return encodeURIComponent(value);
  });
  return missing ? null : filled;
}

export function routeFor(kind: string, data: NotificationData): string {
  const template = ROUTES[kind];
  return (template && fill(template, data)) ?? FALLBACK_ROUTE;
}

export function tagFor(kind: string, data: NotificationData): string {
  const template = TAGS[kind];
  return (template && fill(template, data)) ?? kind;
}

/** Each variant's two sentences, from `en.ts`, the brand filled in. */
export function sentences(): Record<Variant, { named: string; plain: string }> {
  const all = {} as Record<Variant, { named: string; plain: string }>;
  for (const variant of VARIANTS) {
    all[variant] = {
      named: t(`notifications.kinds.${variant}.named`, { app: APP_NAME }),
      plain: t(`notifications.kinds.${variant}.plain`, { app: APP_NAME }),
    };
  }
  return all;
}

/** The sentence for `kind`: with `name` when one is given, else plain. */
export function sentenceFor(
  kind: string,
  data: NotificationData,
  name?: string | null,
): string {
  const variant = variantOf(kind, data);
  return name
    ? t(`notifications.kinds.${variant}.named`, { name, app: APP_NAME })
    : t(`notifications.kinds.${variant}.plain`, { app: APP_NAME });
}
