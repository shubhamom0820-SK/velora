import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import type { Notification } from "@/lib/queries/notifications";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { NotificationsScreen } from "./NotificationsScreen";

const ID = "6f1c2a40-8d1e-4a7b-9c4e-0a2b3c4d5e6f";

function row(overrides: Partial<Notification> = {}): Notification {
  return {
    id: "n1",
    kind: "match",
    data: { match_id: "m1", user_id: ID },
    read_at: null,
    created_at: "2026-10-09T06:30:00Z",
    ...overrides,
  };
}

function routes(items: Notification[], overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/notifications": () => json(200, { items, next_cursor: null }),
    "POST /v1/notifications/read": () => new Response(null, { status: 204 }),
    ...overrides,
  });
}

function renderList() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <NotificationsScreen />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords() {
        return [];
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the in-app list (T-9.4)", () => {
  it("says each kind in en.ts's words and leads where its push would", async () => {
    routes([
      row(),
      row({
        id: "n2",
        kind: "low_balance",
        data: { balance: 6 },
        read_at: "2026-10-09T07:00:00Z",
      }),
    ]);
    renderList();

    const links = within(await screen.findByRole("list")).getAllByRole("link");
    expect(links).toHaveLength(2);
    const [match, low] = links as [HTMLElement, HTMLElement];
    expect(match).toHaveTextContent(t("notifications.kinds.match.plain"));
    expect(match).toHaveTextContent(t("notifications.unread"));
    expect(match).toHaveAttribute("href", `/people/${ID}`);
    expect(low).toHaveAttribute("href", "/wallet");
    expect(low).not.toHaveTextContent(t("notifications.unread"));
  });

  it("leads a gift to its sender's profile (T-8.10)", async () => {
    routes([
      row({
        kind: "gift",
        data: { gift_send_id: "g1", gift_id: "rose", user_id: ID },
      }),
    ]);
    renderList();

    const [link] = within(await screen.findByRole("list")).getAllByRole("link");
    expect(link).toHaveAttribute("href", `/people/${ID}`);
    expect(link).toHaveTextContent(t("notifications.kinds.gift.plain"));
  });

  it("marks them read once, when an unread one has been shown", async () => {
    const api = routes([row()]);
    renderList();

    await screen.findByRole("list");
    await waitFor(() =>
      expect(api.sent()).toContain("POST /v1/notifications/read"),
    );
    expect(
      api.sent().filter((call) => call === "POST /v1/notifications/read"),
    ).toHaveLength(1);
  });

  it("asks nothing to be read when everything already is", async () => {
    const api = routes([row({ read_at: "2026-10-09T07:00:00Z" })]);
    renderList();

    await screen.findByRole("list");
    expect(api.sent()).not.toContain("POST /v1/notifications/read");
  });

  it("has an empty state", async () => {
    routes([]);
    renderList();
    expect(
      await screen.findByText(t("notifications.empty")),
    ).toBeInTheDocument();
  });

  it("has an error state that tries again", async () => {
    let calls = 0;
    routes([], {
      "GET /v1/notifications": () => {
        calls += 1;
        return calls === 1
          ? json(500, { error: { code: "INTERNAL", message: "x" } })
          : json(200, { items: [], next_cursor: null });
      },
    });
    renderList();

    expect(
      await screen.findByText(t("notifications.failed")),
    ).toBeInTheDocument();
    screen.getByRole("button").click();
    expect(
      await screen.findByText(t("notifications.empty")),
    ).toBeInTheDocument();
  });
});
