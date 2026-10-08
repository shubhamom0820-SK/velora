import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import YouPage from "@/app/(app)/you/page";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

const CATALOGUE = {
  gifts: [
    { id: "coffee", label: "Coffee", asset: "☕", credits: 5 },
    { id: "rose", label: "Rose", asset: "🌹", credits: 10 },
  ],
  free_sends_left: null,
  free_sends_reset_at: null,
};

function received(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    gift_id: "rose",
    sender: {
      id: `m-${id}`,
      first_name: "Arjun",
      username: "arjun",
      main_photo_url: null,
      shows_badge: false,
      is_online: false,
      deleted: false,
    },
    created_at: "2026-10-09T10:00:00Z",
    ...overrides,
  };
}

function me(gender: "female" | "male", showGifts = true) {
  return { id: "u1", gender, profile: { show_gifts: showGifts } };
}

function routes(list: Route, overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/gifts": () => json(200, CATALOGUE),
    "GET /v1/me/gifts": list,
    ...overrides,
  });
}

function renderYou(gender: "female" | "male" = "female", showGifts = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), me(gender, showGifts));
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <YouPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("her gifts in the You tab (T-8.10)", () => {
  it("lists who sent which gift, newest first, each opening his profile, never a price", async () => {
    routes(() =>
      json(200, {
        items: [
          received("g2"),
          received("g1", {
            gift_id: "coffee",
            sender: { ...received("g1").sender, first_name: "Kabir" },
          }),
        ],
        next_cursor: null,
      }),
    );
    renderYou();

    const rose = await screen.findByRole("link", { name: /Rose from Arjun/ });
    expect(rose).toHaveAttribute("href", "/people/m-g2");
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Rose from Arjun");
    expect(items[1]).toHaveTextContent("Coffee from Kabir");
    expect(screen.queryByText(/Vela|Free/)).toBeNull();
    // Her You page keeps T-8.8's link to her album's requests.
    expect(
      screen.getByRole("link", { name: t("albumRequests.title") }),
    ).toHaveAttribute("href", "/you/album-requests");
  });

  it("names a deleted sender as such, with no link, and a retired gift as a gift", async () => {
    routes(() =>
      json(200, {
        items: [
          received("g1", {
            gift_id: "wave",
            sender: {
              ...received("g1").sender,
              first_name: null,
              deleted: true,
            },
          }),
        ],
        next_cursor: null,
      }),
    );
    renderYou();

    expect(
      await screen.findByText("A gift from Deleted account"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Deleted account/ })).toBeNull();
  });

  it("asks for the next page when there is one", async () => {
    const api = routes((call) =>
      call.query.get("cursor") === "c1"
        ? json(200, { items: [received("g1")], next_cursor: null })
        : json(200, { items: [received("g2")], next_cursor: "c1" }),
    );
    renderYou();

    await userEvent.click(
      await screen.findByRole("button", { name: t("gifts.more") }),
    );

    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /Rose from/ })).toHaveLength(
        2,
      ),
    );
    expect(api.calls.at(-1)?.query.get("cursor")).toBe("c1");
    expect(screen.queryByRole("button", { name: t("gifts.more") })).toBeNull();
  });

  it("says when there are none yet", async () => {
    routes(() => json(200, { items: [], next_cursor: null }));
    renderYou();

    expect(await screen.findByText(t("gifts.empty"))).toBeInTheDocument();
  });

  it("says when they didn't load, and tries again", async () => {
    let fail = true;
    routes(() =>
      fail
        ? envelope(429, "RATE_LIMITED")
        : json(200, { items: [received("g1")], next_cursor: null }),
    );
    renderYou();

    const message = await screen.findByText(t("gifts.listFailed"));
    const alert = message.closest<HTMLElement>('[role="alert"]');
    if (!alert) throw new Error("the error isn't announced as an alert");
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(
      await screen.findByRole("link", { name: /Rose from Arjun/ }),
    ).toBeInTheDocument();
  });

  it("turns show_gifts off with that switch alone, and reads the answer", async () => {
    const api = routes(() => json(200, { items: [], next_cursor: null }), {
      "PATCH /v1/me/settings": () => json(200, me("female", false)),
    });
    const client = renderYou();

    const toggle = await screen.findByRole("switch", { name: t("gifts.show") });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await userEvent.click(toggle);

    await waitFor(() =>
      expect(toggle).toHaveAttribute("aria-checked", "false"),
    );
    expect(api.calls.find((c) => c.method === "PATCH")?.body).toEqual({
      show_gifts: false,
    });
    expect(
      client.getQueryData<{ profile: { show_gifts: boolean } }>(queryKeys.me())
        ?.profile.show_gifts,
    ).toBe(false);
  });

  it("says when the switch couldn't change, and leaves it as it was", async () => {
    routes(() => json(200, { items: [], next_cursor: null }), {
      "PATCH /v1/me/settings": () => envelope(429, "RATE_LIMITED"),
    });
    renderYou("female", false);

    const toggle = await screen.findByRole("switch", { name: t("gifts.show") });
    await userEvent.click(toggle);

    expect(await screen.findByText(t("gifts.saveFailed"))).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("isn't shown to a man, who asks for no gifts", async () => {
    const api = routes(() => json(200, { items: [], next_cursor: null }));
    renderYou("male");

    expect(
      screen.getByRole("heading", { level: 1, name: t("placeholder.you") }),
    ).toBeInTheDocument();
    expect(screen.queryByText(t("gifts.yours"))).toBeNull();
    expect(api.calls).toEqual([]);
  });
});
