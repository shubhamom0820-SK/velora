import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { AdminUserDetail } from "@/lib/queries/admin";
import { fakeApi } from "@/lib/testing/fakeApi";

import { MinorReview } from "./MinorReview";

const REASON = "Her other photos and her bio read as an adult.";

function detail(overrides: Partial<AdminUserDetail> = {}): AdminUserDetail {
  return {
    user: {
      id: "w1",
      first_name: "Asha",
      username: null,
      city: null,
      gender: "female",
      age: 19,
      role: "user",
      status: "active",
      onboarding_step: "done",
      erased: false,
      deleted_requested_at: null,
      last_active_at: null,
      created_at: new Date().toISOString(),
    },
    phone: null,
    phone_masked: false,
    is_verified: false,
    balance: 0,
    ban: null,
    minor_flags: {
      flags: 2,
      scores: [0.412, 0.93],
      times: [new Date().toISOString(), new Date().toISOString()],
      first_at: new Date().toISOString(),
      last_at: new Date().toISOString(),
    },
    photos: [],
    fraud: null,
    reports_about: [],
    reports_by: [],
    ledger: [],
    threads: [],
    ...overrides,
  };
}

function renderReview(data: AdminUserDetail, isAdmin: boolean) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MinorReview detail={data} isAdmin={isAdmin} />
    </QueryClientProvider>,
  );
}

const button = (key: Parameters<typeof t>[0]) =>
  screen.queryByRole("button", { name: t(key) });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("a possible minor waiting for a review (P-72)", () => {
  it("shows the scores, never a photo", () => {
    renderReview(detail(), true);

    expect(
      screen.getByText(
        t("admin.minorFlags.flags", { count: 2, scores: "0.41, 0.93" }),
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("offers an admin all three decisions", () => {
    renderReview(detail(), true);

    expect(button("admin.minorFlags.adult")).toBeInTheDocument();
    expect(button("admin.minorFlags.freeze")).toBeInTheDocument();
    expect(button("admin.minorFlags.underage")).toBeInTheDocument();
  });

  it("offers a moderator the freeze alone (D-1050)", () => {
    renderReview(detail(), false);

    expect(button("admin.minorFlags.freeze")).toBeInTheDocument();
    expect(button("admin.minorFlags.adult")).not.toBeInTheDocument();
    expect(button("admin.minorFlags.underage")).not.toBeInTheDocument();
  });

  it("offers no freeze to someone who can't sign in", () => {
    renderReview(
      detail({ user: { ...detail().user, status: "banned" } }),
      true,
    );

    expect(button("admin.minorFlags.freeze")).not.toBeInTheDocument();
    expect(button("admin.minorFlags.underage")).toBeInTheDocument();
  });

  it("shows nothing for someone not waiting", () => {
    const { container } = renderReview(detail({ minor_flags: null }), true);

    expect(container).toBeEmptyDOMElement();
  });

  it("says the underage ban can't be undone, and sends it with the reason", async () => {
    const api = fakeApi({
      "POST /v1/admin/users/w1/minor-decision": () =>
        new Response(null, { status: 204 }),
    });
    renderReview(detail(), true);

    await userEvent.click(button("admin.minorFlags.underage")!);
    const sheet = screen.getByRole("dialog");
    expect(
      within(sheet).getByText(t("admin.minorFlags.underageWarning")),
    ).toBeInTheDocument();
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      REASON,
    );
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("admin.minorFlags.underage"),
      }),
    );

    await waitFor(() =>
      expect(api.calls.find((call) => call.method === "POST")?.body).toEqual({
        decision: "underage",
        reason: REASON,
      }),
    );
  });

  it("asks no warning for leaving an adult", async () => {
    renderReview(detail(), true);

    await userEvent.click(button("admin.minorFlags.adult")!);

    expect(
      within(screen.getByRole("dialog")).queryByText(
        t("admin.minorFlags.underageWarning"),
      ),
    ).not.toBeInTheDocument();
  });
});
