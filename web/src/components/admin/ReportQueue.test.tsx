import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { ReportQueue } from "./ReportQueue";

const HOUR = 60 * 60 * 1000;
const NOTE = "Asked her for money twice.";

function report(overrides: Record<string, unknown> = {}) {
  return {
    id: "r1",
    reporter: {
      id: "w1",
      first_name: "Priya",
      username: "priya",
      status: "active",
    },
    reported: {
      id: "m1",
      first_name: "Rohit",
      username: "rohit",
      status: "active",
    },
    reason: "scam",
    details: "He wanted money.",
    thread_id: "t1",
    status: "open",
    action: null,
    resolved_by: null,
    resolved_at: null,
    created_at: new Date(Date.now() - 30 * HOUR).toISOString(),
    due_at: new Date(Date.now() - 6 * HOUR).toISOString(),
    ...overrides,
  };
}

function renderQueue(role: "moderator" | "admin") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "s1", role });
  render(
    <QueryClientProvider client={client}>
      <ReportQueue />
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

describe("the report queue (T-9.5, D-921)", () => {
  it("shows each report with its day, who it is about, and the chat", async () => {
    fakeApi({
      "GET /v1/admin/reports": () =>
        json(200, { items: [report()], next_cursor: null }),
    });

    renderQueue("moderator");

    expect(
      await screen.findByText(t("admin.reports.reasons.scam")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("admin.reports.overdue", { hours: 6 })),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: t("admin.reports.about", { name: "Rohit" }),
      }),
    ).toHaveAttribute("href", "/admin/users/m1");
    expect(
      screen.getByRole("link", { name: t("admin.reports.readChat") }),
    ).toHaveAttribute("href", "/admin/threads/t1?report=r1");
  });

  it("says so when there is nothing open", async () => {
    fakeApi({
      "GET /v1/admin/reports": () =>
        json(200, { items: [], next_cursor: null }),
    });

    renderQueue("moderator");

    expect(
      await screen.findByText(t("admin.reports.empty")),
    ).toBeInTheDocument();
  });

  it("says so when the queue didn't load", async () => {
    fakeApi({ "GET /v1/admin/reports": () => envelope(500, "INTERNAL") });

    renderQueue("moderator");

    expect(await screen.findByText(t("admin.failed"))).toBeInTheDocument();
  });

  it("resolves only once an action is picked and the note says why", async () => {
    const api = fakeApi({
      "GET /v1/admin/reports": () =>
        json(200, { items: [report()], next_cursor: null }),
      "POST /v1/admin/reports/r1/resolve": () =>
        new Response(null, { status: 204 }),
    });
    renderQueue("moderator");
    await userEvent.click(
      await screen.findByRole("button", { name: t("admin.reports.resolve") }),
    );
    const sheet = screen.getByRole("dialog");
    const confirm = within(sheet).getByRole("button", {
      name: t("admin.reports.resolve"),
    });

    expect(confirm).toBeDisabled();
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("admin.reports.actions.freeze"),
      }),
    );
    expect(confirm).toBeDisabled();
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      NOTE,
    );
    await userEvent.click(confirm);

    await waitFor(() =>
      expect(api.calls.find((call) => call.method === "POST")?.body).toEqual({
        action: "freeze",
        note: NOTE,
      }),
    );
  });

  it("never offers a moderator a ban, and offers an admin one", async () => {
    fakeApi({
      "GET /v1/admin/reports": () =>
        json(200, { items: [report()], next_cursor: null }),
    });
    renderQueue("moderator");
    await userEvent.click(
      await screen.findByRole("button", { name: t("admin.reports.resolve") }),
    );

    expect(
      within(screen.getByRole("dialog")).queryByRole("button", {
        name: t("admin.reports.actions.ban"),
      }),
    ).not.toBeInTheDocument();
  });

  it("says why the API refused", async () => {
    fakeApi({
      "GET /v1/admin/reports": () =>
        json(200, { items: [report()], next_cursor: null }),
      "POST /v1/admin/reports/r1/resolve": () =>
        envelope(422, "NOT_ALLOWED", { why: "resolved" }),
    });
    renderQueue("admin");
    await userEvent.click(
      await screen.findByRole("button", { name: t("admin.reports.resolve") }),
    );
    const sheet = screen.getByRole("dialog");
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("admin.reports.actions.ban"),
      }),
    );
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      NOTE,
    );
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("admin.reports.resolve") }),
    );

    expect(
      await within(sheet).findByText(t("admin.refused", { why: "resolved" })),
    ).toBeInTheDocument();
  });
});
