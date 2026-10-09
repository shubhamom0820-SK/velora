/**
 * The browser's side of Web Push (T-9.4): the only code that touches the
 * service worker, `Notification` and `PushManager`. The API's side is the
 * hooks in `queries/notifications.ts`, which send what this returns.
 *
 * What a browser can do, in order of what stops it:
 * - `unsupported`: no service worker, no Push API, or not a secure context.
 * - `ios-install`: an iPhone or iPad in Safari's tab, which has the Push API
 *   only for a web app added to the Home Screen (iOS 16.4 and later).
 * - `denied`: the person blocked notifications for this site; only the
 *   browser's settings undo it.
 * - `ready`: permission not asked yet, or given.
 */

export type PushSupport = "unsupported" | "ios-install" | "denied" | "ready";

/** The subscription as the API takes it (`POST /push/subscriptions`). */
export type PushSubscriptionBody = {
  endpoint: string;
  keys: { p256dh: string; auth: string };
};

export const SERVICE_WORKER_URL = "/sw.js";

/** A window as far as push goes: either API may be missing. */
type PushWindow = Window & {
  Notification?: typeof Notification;
  PushManager?: unknown;
};

function notificationOf(win: Window): typeof Notification | undefined {
  return (win as PushWindow).Notification;
}

function isIos(nav: Navigator): boolean {
  // iPadOS reports itself as a Mac, but a Mac has no touch screen.
  return (
    /iPad|iPhone|iPod/.test(nav.userAgent) ||
    (nav.platform === "MacIntel" && nav.maxTouchPoints > 1)
  );
}

function isInstalled(win: Window): boolean {
  const standalone = (win.navigator as Navigator & { standalone?: boolean })
    .standalone;
  return (
    standalone === true ||
    win.matchMedia?.("(display-mode: standalone)").matches === true
  );
}

export function pushSupport(win: Window = window): PushSupport {
  const nav = win.navigator;
  const notification = notificationOf(win);
  const hasPush =
    win.isSecureContext &&
    "serviceWorker" in nav &&
    (win as PushWindow).PushManager !== undefined &&
    notification !== undefined;
  if (!hasPush || !notification) {
    return isIos(nav) && !isInstalled(win) ? "ios-install" : "unsupported";
  }
  return notification.permission === "denied" ? "denied" : "ready";
}

export function permission(
  win: Window = window,
): NotificationPermission | null {
  return notificationOf(win)?.permission ?? null;
}

/** The VAPID key as `applicationServerKey` wants it: bytes, from base64url. */
export function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

function bodyOf(subscription: PushSubscription): PushSubscriptionBody {
  const json = subscription.toJSON();
  const p256dh = json.keys?.p256dh;
  const auth = json.keys?.auth;
  if (!json.endpoint || !p256dh || !auth) {
    throw new Error("The browser's subscription has no keys");
  }
  return { endpoint: json.endpoint, keys: { p256dh, auth } };
}

/**
 * Ask for permission (in the tap that called this: browsers refuse an ask
 * nobody tapped for), register `/sw.js`, and subscribe with the API's key.
 * Null when the person said no.
 */
export async function subscribe(
  publicKey: string,
  win: Window = window,
): Promise<PushSubscriptionBody | null> {
  const notification = notificationOf(win);
  if (!notification) return null;
  const answer = await notification.requestPermission();
  if (answer !== "granted") return null;
  const registration = await win.navigator.serviceWorker.register(
    SERVICE_WORKER_URL,
    { scope: "/" },
  );
  const ready = await win.navigator.serviceWorker.ready;
  const manager = (ready ?? registration).pushManager;
  const existing = await manager.getSubscription();
  const subscription =
    existing ??
    (await manager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(publicKey),
    }));
  return bodyOf(subscription);
}

/** This browser's subscription, if it has one. */
export async function current(
  win: Window = window,
): Promise<PushSubscriptionBody | null> {
  if (!("serviceWorker" in win.navigator)) return null;
  const registration = await win.navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  return subscription ? bodyOf(subscription) : null;
}

/** Unsubscribe this browser; the endpoint it had, for the API to forget. */
export async function unsubscribe(
  win: Window = window,
): Promise<string | null> {
  if (!("serviceWorker" in win.navigator)) return null;
  const registration = await win.navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return null;
  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  return endpoint;
}

const ASKED_KEY = "push.asked";

/**
 * Whether the after-the-first-match ask was already shown in this browser.
 * A convenience only: storage can be blocked, and then it asks again.
 */
export function askedBefore(win: Window = window): boolean {
  try {
    return win.localStorage.getItem(ASKED_KEY) === "1";
  } catch {
    return false;
  }
}

export function rememberAsked(win: Window = window): void {
  try {
    win.localStorage.setItem(ASKED_KEY, "1");
  } catch {
    // Blocked storage: it asks again next match, which is harmless.
  }
}
