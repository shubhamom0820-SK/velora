import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { PushAsk } from "./PushAsk";

// RFC 8291 §5's example public key: published, and a public key besides.
// prettier-ignore
const KEY = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"; // gitleaks:allow
const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1";

function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/push/key": () => json(200, { public_key: KEY }),
    "POST /v1/push/subscriptions": () =>
      json(201, { endpoint: "https://fcm.googleapis.com/fcm/send/x" }),
    ...overrides,
  });
}

function renderAsk() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <PushAsk />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** A browser with the Push API, its permission not asked yet. */
function canPush(permission: NotificationPermission = "default") {
  const requestPermission = vi.fn().mockResolvedValue("granted");
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("PushManager", class {});
  vi.stubGlobal("Notification", { permission, requestPermission });
  const manager = {
    getSubscription: vi.fn().mockResolvedValue(null),
    subscribe: vi.fn().mockResolvedValue({
      toJSON: () => ({
        endpoint: "https://fcm.googleapis.com/fcm/send/x",
        keys: { p256dh: "P", auth: "A" },
      }),
    }),
  };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      register: vi.fn().mockResolvedValue({ pushManager: manager }),
      ready: Promise.resolve({ pushManager: manager }),
    },
  });
  return { requestPermission, manager };
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  Reflect.deleteProperty(navigator, "serviceWorker");
  vi.restoreAllMocks();
});

describe("asking for notifications after a match (T-9.4)", () => {
  it("asks once per browser, and the browser's prompt waits for the tap", async () => {
    const api = routes();
    const { requestPermission } = canPush();
    const first = renderAsk();

    const turnOn = await screen.findByRole("button", {
      name: t("notifications.ask.turnOn"),
    });
    expect(requestPermission).not.toHaveBeenCalled();
    await userEvent.click(turnOn);

    await waitFor(() =>
      expect(api.sent()).toContain("POST /v1/push/subscriptions"),
    );
    expect(requestPermission).toHaveBeenCalledOnce();
    const sent = api.calls.find((call) => call.method === "POST");
    expect(sent?.body).toEqual({
      endpoint: "https://fcm.googleapis.com/fcm/send/x",
      keys: { p256dh: "P", auth: "A" },
    });
    first.unmount();
    const keyCalls = () =>
      api.sent().filter((call) => call === "GET /v1/push/key").length;
    const before = keyCalls();

    // The next match: never asked again, and the key never asked for. Long
    // enough for the key to have come back, had it been asked.
    renderAsk();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      screen.queryByRole("button", { name: t("notifications.ask.turnOn") }),
    ).not.toBeInTheDocument();
    expect(keyCalls()).toBe(before);
  });

  it("asks nothing where this build has no push", async () => {
    routes({ "GET /v1/push/key": () => envelope(404, "NOT_FOUND") });
    canPush();
    renderAsk();

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(
      screen.queryByRole("button", { name: t("notifications.ask.turnOn") }),
    ).not.toBeInTheDocument();
  });

  it("asks nothing once the person has decided, and requests nothing", async () => {
    const api = routes();
    canPush("denied");
    renderAsk();

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(
      screen.queryByRole("button", { name: t("notifications.ask.turnOn") }),
    ).not.toBeInTheDocument();
    expect(api.sent()).toEqual([]);
  });

  it("tells an iPhone in Safari's tab how, instead of asking", async () => {
    routes();
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(IPHONE);
    renderAsk();

    expect(
      await screen.findByText(
        t("notifications.settings.iosInstall", { app: APP_NAME }),
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("notifications.ask.turnOn") }),
    ).not.toBeInTheDocument();
  });
});
