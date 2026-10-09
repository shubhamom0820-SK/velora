import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import type { Prefs } from "@/lib/queries/notifications";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { NotificationSettings } from "./NotificationSettings";

const DEFAULTS: Prefs = {
  match: true,
  message: true,
  like: true,
  knot: true,
  expiry: true,
  balance: true,
  gift: true,
  album: true,
  generic_text: false,
};

function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/notification-prefs": () => json(200, DEFAULTS),
    "GET /v1/push/key": () => envelope(404, "NOT_FOUND"),
    ...overrides,
  });
}

function renderSettings(gender: "male" | "female") {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  client.setQueryData(queryKeys.me(), { id: "u1", gender });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <NotificationSettings />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("notification settings (T-9.4)", () => {
  it("never shows her a switch about an hour running out, nor a balance (P-460)", async () => {
    routes();
    renderSettings("female");

    await screen.findByRole("switch", {
      name: t("notifications.settings.match"),
    });
    expect(
      screen.queryByRole("switch", {
        name: t("notifications.settings.expiry"),
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("switch", {
        name: t("notifications.settings.balance"),
      }),
    ).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/run out|running out|expire/i);
  });

  it("shows him both", async () => {
    routes();
    renderSettings("male");

    expect(
      await screen.findByRole("switch", {
        name: t("notifications.settings.expiry"),
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: t("notifications.settings.balance") }),
    ).toBeInTheDocument();
  });

  it("saves one switch at a time and shows what was saved", async () => {
    const api = routes({
      "PATCH /v1/notification-prefs": (call) => {
        expect(call.body).toEqual({ gift: false });
        return json(200, { ...DEFAULTS, gift: false });
      },
    });
    renderSettings("female");

    const gift = await screen.findByRole("switch", {
      name: t("notifications.settings.gift"),
    });
    expect(gift).toHaveAttribute("aria-checked", "true");
    await userEvent.click(gift);

    await waitFor(() => expect(gift).toHaveAttribute("aria-checked", "false"));
    expect(api.sent()).toContain("PATCH /v1/notification-prefs");
  });

  it("says when a save fails", async () => {
    routes({
      "PATCH /v1/notification-prefs": () => envelope(500, "INTERNAL"),
    });
    renderSettings("female");

    await userEvent.click(
      await screen.findByRole("switch", {
        name: t("notifications.settings.like"),
      }),
    );

    expect(
      await screen.findByText(t("notifications.settings.saveFailed")),
    ).toBeInTheDocument();
  });

  it("says this browser has no push where the build has none", async () => {
    routes();
    renderSettings("female");

    expect(
      await screen.findByText(t("notifications.settings.unavailable")),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("switch", {
        name: t("notifications.settings.device"),
      }),
    ).not.toBeInTheDocument();
  });

  it("has an error state", async () => {
    routes({ "GET /v1/notification-prefs": () => envelope(500, "INTERNAL") });
    renderSettings("female");

    expect(
      await screen.findByText(t("notifications.settings.failed")),
    ).toBeInTheDocument();
  });

  it("names the brand from APP_NAME in the iPhone note", () => {
    expect(t("notifications.settings.iosInstall", { app: APP_NAME })).toContain(
      APP_NAME,
    );
  });
});
