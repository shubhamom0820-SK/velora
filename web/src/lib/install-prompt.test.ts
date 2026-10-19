import { afterEach, describe, expect, it, vi } from "vitest";

import {
  dismiss,
  dismissedBefore,
  install,
  offer,
  subscribe,
} from "./install-prompt";

const ANDROID =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36";
const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1";

/** This window as a phone, a desktop, or an installed app. */
function device({ touch = true, standalone = false, agent = ANDROID } = {}) {
  window.matchMedia = ((query: string) => ({
    matches:
      (query === "(hover: none) and (pointer: coarse)" && touch) ||
      (query === "(display-mode: standalone)" && standalone),
  })) as unknown as typeof window.matchMedia;
  vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(agent);
}

type Offered = Event & { prompt: ReturnType<typeof vi.fn> };

/** The browser offers to install the app, as Chrome does. */
function browserOffers(
  outcome: "accepted" | "dismissed" = "accepted",
): Offered {
  const event = new Event("beforeinstallprompt", { cancelable: true });
  Object.assign(event, {
    prompt: vi.fn(() => Promise.resolve()),
    userChoice: Promise.resolve({ outcome }),
  });
  window.dispatchEvent(event);
  return event as Offered;
}

afterEach(() => {
  window.dispatchEvent(new Event("appinstalled"));
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("what the install banner offers (T-9.7, D-1042)", () => {
  it("holds Android's offer, keeping the browser's own bar away", () => {
    device();
    const event = browserOffers();
    expect(event.defaultPrevented).toBe(true);
    expect(offer()).toBe("android");
  });

  it("offers nothing on Android until the browser does", () => {
    device();
    expect(offer()).toBe("none");
  });

  it("tells an iPhone the steps, since Safari has no prompt", () => {
    device({ agent: IPHONE });
    expect(offer()).toBe("ios");
  });

  it("offers nothing on a desktop, even when the browser offers (phones only)", () => {
    device({ touch: false });
    browserOffers();
    expect(offer()).toBe("none");
    device({ touch: false, agent: IPHONE });
    expect(offer()).toBe("none");
  });

  it("offers nothing once the app is installed", () => {
    device({ standalone: true });
    browserOffers();
    expect(offer()).toBe("none");
    device({ standalone: true, agent: IPHONE });
    expect(offer()).toBe("none");
  });

  it("forgets the offer when the app is installed from elsewhere", () => {
    device();
    browserOffers();
    window.dispatchEvent(new Event("appinstalled"));
    expect(offer()).toBe("none");
  });
});

describe("closing the banner", () => {
  it("is remembered in this browser, so it never comes back", () => {
    device({ agent: IPHONE });
    const told = vi.fn();
    const stop = subscribe(told);
    dismiss();
    stop();

    expect(told).toHaveBeenCalled();
    expect(dismissedBefore()).toBe(true);
    expect(offer()).toBe("none");
    device();
    browserOffers();
    expect(offer()).toBe("none");
  });

  it("shows again, harmlessly, where storage is blocked", () => {
    const blocked = {
      get localStorage(): Storage {
        throw new Error("blocked");
      },
    } as unknown as Window;
    expect(() => dismiss(blocked)).not.toThrow();
    expect(dismissedBefore(blocked)).toBe(false);
  });
});

describe("installing", () => {
  it("opens the browser's own dialog once, and the offer is used", async () => {
    device();
    const event = browserOffers("accepted");

    await install();

    expect(event.prompt).toHaveBeenCalledOnce();
    expect(offer()).toBe("none");
    expect(dismissedBefore()).toBe(false);
    await install();
    expect(event.prompt).toHaveBeenCalledOnce();
  });

  it("turned down in the browser's dialog, it is closed for good", async () => {
    device();
    browserOffers("dismissed");
    await install();
    expect(dismissedBefore()).toBe(true);
  });
});
