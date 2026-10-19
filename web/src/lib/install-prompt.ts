import { isInstalled, isIos } from "./push";

/**
 * What the install banner offers (T-9.7, D-1042):
 * - `android`: the browser offered to install the app (`beforeinstallprompt`,
 *   Chrome and the browsers built on it), held here until the tap.
 * - `ios`: an iPhone or iPad, where Safari has no prompt, so the banner says
 *   the steps: Share, then Add to Home Screen.
 * - `none`: already installed, closed before, a desktop, or nothing offered.
 *
 * Touch-first devices only (`(hover: none) and (pointer: coarse)`): the copy
 * says Home Screen, which a desktop doesn't have (the founder, T-9.7's plan).
 */
export type InstallOffer = "android" | "ios" | "none";

/** The event Chrome fires; not in TypeScript's DOM types yet. */
type InstallPromptEvent = Event & {
  prompt: () => Promise<unknown>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const DISMISSED_KEY = "install.dismissed";

let held: InstallPromptEvent | null = null;
const readers = new Set<() => void>();

function changed(): void {
  for (const reader of readers) reader();
}

/**
 * Catch the browser's offer and keep it (its own mini-infobar shows nothing
 * then), and forget it once the app is installed. Called as this module
 * loads, so an offer fired before React has drawn the banner isn't missed.
 */
export function listen(win: Window = window): () => void {
  const offered = (event: Event) => {
    event.preventDefault();
    held = event as InstallPromptEvent;
    changed();
  };
  const installed = () => {
    held = null;
    changed();
  };
  win.addEventListener("beforeinstallprompt", offered);
  win.addEventListener("appinstalled", installed);
  return () => {
    win.removeEventListener("beforeinstallprompt", offered);
    win.removeEventListener("appinstalled", installed);
  };
}

if (typeof window !== "undefined") listen();

/** For `useSyncExternalStore`: told whenever the offer may have changed. */
export function subscribe(reader: () => void): () => void {
  readers.add(reader);
  return () => {
    readers.delete(reader);
  };
}

function touchFirst(win: Window): boolean {
  return (
    win.matchMedia?.("(hover: none) and (pointer: coarse)").matches === true
  );
}

/** Closed before in this browser. Storage blocked: never closed, so it shows. */
export function dismissedBefore(win: Window = window): boolean {
  try {
    return win.localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function offer(win: Window = window): InstallOffer {
  if (isInstalled(win) || !touchFirst(win) || dismissedBefore(win)) {
    return "none";
  }
  if (held) return "android";
  return isIos(win.navigator) ? "ios" : "none";
}

/** The banner's close: remembered in this browser, so it never comes back. */
export function dismiss(win: Window = window): void {
  try {
    win.localStorage.setItem(DISMISSED_KEY, "1");
  } catch {
    // Blocked storage: it shows again on the next load, which is harmless.
  }
  changed();
}

/**
 * Show the browser's own install dialog, from the tap that called this. The
 * offer is used once either way; turned down there, it is closed as the
 * banner's own close is, so it doesn't come back.
 */
export async function install(win: Window = window): Promise<void> {
  const event = held;
  if (!event) return;
  held = null;
  changed();
  await event.prompt();
  const choice = await event.userChoice;
  if (choice.outcome === "dismissed") dismiss(win);
}
