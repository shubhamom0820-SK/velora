import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
  type Route,
} from "@/lib/testing/fakeApi";
import { resetSession, useSession } from "@/store/session";

import { SettingsScreen } from "./SettingsScreen";

type Gender = "female" | "male";

function me(gender: Gender, overrides: Record<string, unknown> = {}) {
  return {
    id: "u1",
    status: "active",
    gender,
    age: 27,
    is_verified: true,
    has_pin: true,
    balance: gender === "male" ? 7 : 0,
    profile: {
      first_name: "Rohit",
      username: "rohit_a",
      is_hidden: false,
      hide_age: false,
      hide_distance: false,
      show_kudos: true,
      show_gifts: true,
      public_link: false,
    },
    ...overrides,
  };
}

const NO_EXPORT: Route = () => envelope(404, "NOT_FOUND");

function renderSettings(gender: Gender = "male", overrides = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), me(gender, overrides));
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <SettingsScreen />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  resetSession();
});

afterEach(() => {
  clearCookies();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("privacy switches (T-9.6's PATCH /me/settings)", () => {
  it.each([
    ["settings.hidden", "is_hidden", true],
    ["settings.hideAge", "hide_age", true],
    ["settings.hideDistance", "hide_distance", true],
    ["settings.showKudos", "show_kudos", false],
    ["settings.publicLink", "public_link", true],
  ] as const)("%s sends %s alone", async (label, field, value) => {
    const api = fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "PATCH /v1/me/settings": (call) =>
        json(200, {
          ...me("male"),
          profile: { ...me("male").profile, ...(call.body as object) },
        }),
    });
    renderSettings();

    const toggle = screen.getByRole("switch", { name: t(label) });
    await userEvent.click(toggle);

    await waitFor(() =>
      expect(toggle).toHaveAttribute("aria-checked", String(value)),
    );
    expect(api.calls.find((c) => c.method === "PATCH")?.body).toEqual({
      [field]: value,
    });
  });

  it("leaves show_gifts beside her gifts (T-8.10)", () => {
    fakeApi({ "GET /v1/me/export": NO_EXPORT });
    renderSettings("female");

    expect(screen.queryByRole("switch", { name: t("gifts.show") })).toBeNull();
  });

  it("says when a switch couldn't change, and leaves it", async () => {
    fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "PATCH /v1/me/settings": () => envelope(429, "RATE_LIMITED"),
    });
    renderSettings();

    const toggle = screen.getByRole("switch", { name: t("settings.hideAge") });
    await userEvent.click(toggle);

    expect(
      await screen.findByText(t("settings.saveFailed")),
    ).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });
});

describe("pause (T-9.6)", () => {
  it("pauses, then reads Me again", async () => {
    let status = "active";
    const api = fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "POST /v1/me/pause": () => {
        status = "paused";
        return new Response(null, { status: 204 });
      },
      "GET /v1/me": () => json(200, me("male", { status })),
    });
    useSession.getState().signIn("token");
    renderSettings();

    await userEvent.click(
      screen.getByRole("button", { name: t("settings.pause.button") }),
    );

    expect(
      await screen.findByText(t("settings.pause.paused")),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("POST /v1/me/pause");
    expect(
      screen.getByRole("button", { name: t("settings.pause.resume") }),
    ).toBeInTheDocument();
  });

  it("resumes a paused account", async () => {
    const api = fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "DELETE /v1/me/pause": () => new Response(null, { status: 204 }),
      "GET /v1/me": () => json(200, me("male")),
    });
    useSession.getState().signIn("token");
    renderSettings("male", { status: "paused" });

    await userEvent.click(
      screen.getByRole("button", { name: t("settings.pause.resume") }),
    );

    expect(
      await screen.findByRole("button", { name: t("settings.pause.button") }),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("DELETE /v1/me/pause");
  });
});

describe("a copy of your data (D-502)", () => {
  function exported(status: string, overrides: Record<string, unknown> = {}) {
    return {
      id: "e1",
      status,
      requested_at: "2026-10-09T10:00:00Z",
      expires_at: null,
      url: null,
      ...overrides,
    };
  }

  it("asks for one when none was ever made (NOT_FOUND), then waits for it", async () => {
    const api = fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "POST /v1/me/export": () => json(202, exported("pending")),
    });
    renderSettings();

    await userEvent.click(
      await screen.findByRole("button", { name: t("settings.export.ask") }),
    );

    expect(
      await screen.findByText(t("settings.export.pending")),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("POST /v1/me/export");
  });

  it("links a ready copy until it expires", async () => {
    fakeApi({
      "GET /v1/me/export": () =>
        json(
          200,
          exported("ready", {
            url: "https://files.test/export.json?sig=1",
            expires_at: "2026-10-10T10:00:00Z",
          }),
        ),
    });
    renderSettings();

    const link = await screen.findByRole("link", {
      name: t("settings.export.ready"),
    });
    expect(link).toHaveAttribute(
      "href",
      "https://files.test/export.json?sig=1",
    );
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/The link works until/)).toBeInTheDocument();
  });

  it.each([
    ["expired", "settings.export.askAgain"],
    ["failed", "settings.export.askAgain"],
  ] as const)("offers a new one when the last %s", async (status, label) => {
    fakeApi({ "GET /v1/me/export": () => json(200, exported(status)) });
    renderSettings();

    expect(await screen.findByRole("button", { name: t(label) })).toBeEnabled();
  });

  it("says when the day's copies are used up (RATE_LIMITED)", async () => {
    fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "POST /v1/me/export": () => envelope(429, "RATE_LIMITED"),
    });
    renderSettings();

    await userEvent.click(
      await screen.findByRole("button", { name: t("settings.export.ask") }),
    );

    expect(
      await screen.findByText(t("settings.export.tooMany")),
    ).toBeInTheDocument();
  });

  it("says when it couldn't check, and tries again", async () => {
    let fail = true;
    fakeApi({
      "GET /v1/me/export": () =>
        fail ? envelope(500, "INTERNAL") : envelope(404, "NOT_FOUND"),
    });
    renderSettings();

    const message = await screen.findByText(t("settings.export.loadFailed"));
    fail = false;
    const alert = message.closest<HTMLElement>('[role="alert"]');
    if (!alert) throw new Error("the error isn't announced as an alert");
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(
      await screen.findByRole("button", { name: t("settings.export.ask") }),
    ).toBeInTheDocument();
  });
});

describe("deleting the account (D-500, D-504)", () => {
  async function openSheet() {
    await userEvent.click(
      screen.getByRole("button", { name: t("settings.delete.button") }),
    );
    return screen.findByRole("dialog", {
      name: t("settings.delete.sheetTitle"),
    });
  }

  it("shows his balance from the API in plain words before he confirms", async () => {
    fakeApi({ "GET /v1/me/export": NO_EXPORT });
    renderSettings("male", { balance: 7 });

    const sheet = await openSheet();

    expect(
      within(sheet).getByText(
        /You have 7 Velas\. They're lost when your account is erased/,
      ),
    ).toBeInTheDocument();
    expect(
      within(sheet).getByText(t("settings.delete.restore")),
    ).toBeInTheDocument();
  });

  it("says one Vela as one", async () => {
    fakeApi({ "GET /v1/me/export": NO_EXPORT });
    renderSettings("male", { balance: 1 });

    const sheet = await openSheet();

    expect(
      within(sheet).getByText(/You have 1 Vela\. It's lost/),
    ).toBeInTheDocument();
  });

  it("shows her no balance: she holds no Velas", async () => {
    fakeApi({ "GET /v1/me/export": NO_EXPORT });
    renderSettings("female");

    const sheet = await openSheet();

    expect(sheet).not.toHaveTextContent(/Vela/);
  });

  it("cancels with nothing sent", async () => {
    const api = fakeApi({ "GET /v1/me/export": NO_EXPORT });
    renderSettings();

    const sheet = await openSheet();
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("settings.delete.cancel") }),
    );

    expect(api.sent()).not.toContain("DELETE /v1/me");
  });

  it("deletes, then signs the tab out and forgets everything", async () => {
    const api = fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "DELETE /v1/me": () => json(202, { erase_by: "2026-11-08T10:00:00Z" }),
      "POST /v1/auth/logout": () => envelope(401, "SESSION_REVOKED"),
    });
    // The CSRF cookie sign-in leaves, which the logout sends back (D-055).
    vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
    setCookie("csrf_local", "c1");
    useSession.getState().signIn("token");
    const client = renderSettings();

    const sheet = await openSheet();
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("settings.delete.confirm") }),
    );

    await waitFor(() =>
      expect(useSession.getState().status).toBe("signed-out"),
    );
    expect(api.sent()).toEqual(
      expect.arrayContaining(["DELETE /v1/me", "POST /v1/auth/logout"]),
    );
    expect(client.getQueryData(queryKeys.me())).toBeUndefined();
  });

  it("says when the delete failed, and stays signed in", async () => {
    fakeApi({
      "GET /v1/me/export": NO_EXPORT,
      "DELETE /v1/me": () => envelope(500, "INTERNAL"),
    });
    useSession.getState().signIn("token");
    renderSettings();

    const sheet = await openSheet();
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("settings.delete.confirm") }),
    );

    expect(
      await within(sheet).findByText(t("settings.delete.failed")),
    ).toBeInTheDocument();
    expect(useSession.getState().status).toBe("signed-in");
  });
});
