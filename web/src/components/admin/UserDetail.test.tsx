import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { AdminUserDetail } from "@/lib/queries/admin";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { UserDetail } from "./UserDetail";

const REASON = "Checked against the report and the chat.";

function detail(overrides: Partial<AdminUserDetail> = {}): AdminUserDetail {
  return {
    user: {
      id: "m1",
      first_name: "Rohit",
      username: "rohit",
      city: "Phagwara",
      gender: "male",
      age: 27,
      role: "user",
      status: "active",
      onboarding_step: "done",
      erased: false,
      deleted_requested_at: null,
      last_active_at: null,
      created_at: new Date().toISOString(),
    },
    phone: "+919812345678",
    phone_masked: false,
    is_verified: false,
    balance: 12,
    ban: null,
    photos: [],
    fraud: null,
    reports_about: [],
    reports_by: [],
    ledger: [],
    threads: [],
    ...overrides,
  };
}

function renderDetail(role: "moderator" | "admin") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "s1", role });
  render(
    <QueryClientProvider client={client}>
      <UserDetail id="m1" />
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

describe("one account for staff (T-9.5)", () => {
  it("shows an admin the whole number, the ban and the Velas form", async () => {
    fakeApi({ "GET /v1/admin/users/m1": () => json(200, detail()) });

    renderDetail("admin");

    expect(await screen.findByText(/\+919812345678/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t("admin.user.ban") }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t("admin.user.creditsSubmit") }),
    ).toBeInTheDocument();
  });

  it("shows a moderator the masked number, a freeze, and no ban nor Velas", async () => {
    fakeApi({
      "GET /v1/admin/users/m1": () =>
        json(200, detail({ phone: "+91******5678", phone_masked: true })),
    });

    renderDetail("moderator");

    expect(
      await screen.findByText(t("admin.user.phoneMasked")),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t("admin.user.freeze") }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("admin.user.ban") }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("admin.user.creditsSubmit") }),
    ).not.toBeInTheDocument();
  });

  it("offers an erased account's number a ban, and nothing else", async () => {
    fakeApi({
      "GET /v1/admin/users/m1": () =>
        json(
          200,
          detail({
            phone: null,
            user: { ...detail().user, status: "deleted", erased: true },
          }),
        ),
    });

    renderDetail("admin");

    expect(
      await screen.findByText(t("admin.users.erased")),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t("admin.user.ban") }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("admin.user.freeze") }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("admin.user.creditsSubmit") }),
    ).not.toBeInTheDocument();
  });

  it("freezes behind a confirmation that asks why", async () => {
    const api = fakeApi({
      "GET /v1/admin/users/m1": () => json(200, detail()),
      "POST /v1/admin/users/m1/status": () =>
        new Response(null, { status: 204 }),
    });
    renderDetail("moderator");

    await userEvent.click(
      await screen.findByRole("button", { name: t("admin.user.freeze") }),
    );
    const sheet = screen.getByRole("dialog");
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      REASON,
    );
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("admin.user.freeze") }),
    );

    await waitFor(() =>
      expect(api.calls.find((call) => call.method === "POST")?.body).toEqual({
        status: "frozen",
        reason: REASON,
      }),
    );
  });

  it("sends a change of Velas with one key, the same on a retry", async () => {
    let tries = 0;
    const api = fakeApi({
      "GET /v1/admin/users/m1": () => json(200, detail()),
      "POST /v1/admin/users/m1/credits": () =>
        ++tries === 1
          ? envelope(500, "INTERNAL")
          : new Response(null, { status: 204 }),
    });
    renderDetail("admin");
    await userEvent.click(
      await screen.findByRole("button", {
        name: t("admin.user.creditsSubmit"),
      }),
    );
    const sheet = screen.getByRole("dialog");
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.user.delta")),
      "-4",
    );
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      REASON,
    );
    const confirm = within(sheet).getByRole("button", {
      name: t("admin.user.creditsSubmit"),
    });

    await userEvent.click(confirm);
    expect(
      await within(sheet).findByText(t("admin.refused", { why: "INTERNAL" })),
    ).toBeInTheDocument();
    await userEvent.click(confirm);

    await waitFor(() => expect(tries).toBe(2));
    const posts = api.calls.filter((call) => call.method === "POST");
    expect(posts.map((call) => call.body)).toEqual([
      { delta: -4, reason: REASON },
      { delta: -4, reason: REASON },
    ]);
    const keys = posts.map((call) => call.headers.get("Idempotency-Key"));
    expect(keys[0]).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(keys[1]).toBe(keys[0]);
  });

  it("says so when the account didn't load", async () => {
    fakeApi({ "GET /v1/admin/users/m1": () => envelope(404, "NOT_FOUND") });

    renderDetail("admin");

    expect(await screen.findByText(t("admin.failed"))).toBeInTheDocument();
  });
});
