import { describe, expect, it, vi } from "vitest";

import {
  askedBefore,
  keyBytes,
  pushSupport,
  rememberAsked,
  subscribe,
} from "./push";

type Fake = Partial<Omit<Window, "navigator">> & {
  navigator: Partial<Navigator> & { standalone?: boolean };
};

function browser({
  push = true,
  secure = true,
  permission = "default" as NotificationPermission,
  agent = "Mozilla/5.0 (X11; Linux x86_64) Chrome/130",
  standalone = false,
} = {}): Window {
  const fake: Fake = {
    isSecureContext: secure,
    matchMedia: ((query: string) => ({
      matches: standalone && query === "(display-mode: standalone)",
    })) as unknown as Window["matchMedia"],
    navigator: {
      userAgent: agent,
      platform: "Linux",
      maxTouchPoints: 0,
      ...(push ? { serviceWorker: {} as ServiceWorkerContainer } : {}),
    },
  };
  if (push) {
    Object.assign(fake, {
      PushManager: class {},
      Notification: { permission, requestPermission: vi.fn() },
    });
  }
  return fake as unknown as Window;
}

const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1";

describe("what this browser can do (T-9.4)", () => {
  it("is ready where the Push API is and nobody has said no", () => {
    expect(pushSupport(browser())).toBe("ready");
    expect(pushSupport(browser({ permission: "granted" }))).toBe("ready");
  });

  it("is denied once the person blocked notifications", () => {
    expect(pushSupport(browser({ permission: "denied" }))).toBe("denied");
  });

  it("is unsupported without the Push API or off a secure page", () => {
    expect(pushSupport(browser({ push: false }))).toBe("unsupported");
    expect(pushSupport(browser({ secure: false }))).toBe("unsupported");
  });

  it("tells an iPhone in Safari's tab to add the app to its Home Screen", () => {
    expect(pushSupport(browser({ push: false, agent: IPHONE }))).toBe(
      "ios-install",
    );
  });

  it("is ready on an iPhone once the app is on the Home Screen", () => {
    expect(pushSupport(browser({ agent: IPHONE, standalone: true }))).toBe(
      "ready",
    );
  });
});

describe("the VAPID key", () => {
  it("turns base64url into its 65 bytes", () => {
    const key =
      "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4";
    const bytes = keyBytes(key);
    expect(bytes).toHaveLength(65);
    expect(bytes[0]).toBe(4);
  });
});

describe("subscribing", () => {
  it("does nothing more when the person says no to the browser's ask", async () => {
    const win = browser();
    const register = vi.fn();
    Object.assign(win.navigator, { serviceWorker: { register } });
    vi.mocked(
      (win as unknown as { Notification: typeof Notification }).Notification
        .requestPermission,
    ).mockResolvedValue("denied");

    expect(await subscribe("key", win)).toBeNull();
    expect(register).not.toHaveBeenCalled();
  });

  it("registers /sw.js and sends the endpoint and keys, never more", async () => {
    const win = browser();
    vi.mocked(
      (win as unknown as { Notification: typeof Notification }).Notification
        .requestPermission,
    ).mockResolvedValue("granted");
    const subscription = {
      toJSON: () => ({
        endpoint: "https://fcm.googleapis.com/fcm/send/x",
        expirationTime: null,
        keys: { p256dh: "P", auth: "A" },
      }),
    };
    const manager = {
      getSubscription: vi.fn().mockResolvedValue(null),
      subscribe: vi.fn().mockResolvedValue(subscription),
    };
    const register = vi.fn().mockResolvedValue({ pushManager: manager });
    Object.assign(win.navigator, {
      serviceWorker: {
        register,
        ready: Promise.resolve({ pushManager: manager }),
      },
    });

    const body = await subscribe("AAAA", win);

    expect(register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
    expect(manager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    expect(body).toEqual({
      endpoint: "https://fcm.googleapis.com/fcm/send/x",
      keys: { p256dh: "P", auth: "A" },
    });
  });
});

describe("the once-per-browser ask", () => {
  it("is remembered", () => {
    const store = new Map<string, string>();
    const win = {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => store.set(key, value),
      },
    } as unknown as Window;
    expect(askedBefore(win)).toBe(false);
    rememberAsked(win);
    expect(askedBefore(win)).toBe(true);
  });

  it("asks again, harmlessly, where storage is blocked", () => {
    const blocked = {
      get localStorage(): Storage {
        throw new Error("blocked");
      },
    } as unknown as Window;
    expect(() => rememberAsked(blocked)).not.toThrow();
    expect(askedBefore(blocked)).toBe(false);
  });
});
