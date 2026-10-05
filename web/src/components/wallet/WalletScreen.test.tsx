import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import type { LedgerEntry } from "@/lib/queries/wallet";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { entryTime } from "./LedgerHistory";
import { priceRows } from "./PriceList";
import { WalletScreen } from "./WalletScreen";

// A brand that is neither the prototype's nor ours (CLAUDE.md rule 17).
vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));

/** `/prices` as the API sends it: every active action, by name (T-5.2). */
const PRICES = {
  album_request: 1,
  dm_message: 2,
  dm_open: 8,
  liked_you_reveal: 20,
  super_like: 5,
  thread_extend: 10,
  thread_open: 5,
  thread_reopen: 2,
  voice_unlock: 5,
};

function entry(overrides: Partial<LedgerEntry> = {}): LedgerEntry {
  return {
    id: "e1",
    delta: -5,
    balance_after: 25,
    reason: "thread_open",
    created_at: "2026-10-05T09:12:00Z",
    ...overrides,
  };
}

/** jsdom has no IntersectionObserver: this one is told when the end shows. */
class FakeObserver {
  static live = new Set<FakeObserver>();
  constructor(private readonly callback: IntersectionObserverCallback) {}
  observe() {
    FakeObserver.live.add(this);
  }
  disconnect() {
    FakeObserver.live.delete(this);
  }
  unobserve() {}
  takeRecords() {
    return [];
  }
  intersect() {
    this.callback(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    );
  }
}

/** The end of the history scrolls into view. */
function scrollToEnd() {
  act(() => {
    for (const observer of [...FakeObserver.live]) observer.intersect();
  });
}

function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/wallet": () => json(200, { balance: 30 }),
    "GET /v1/prices": () => json(200, PRICES),
    "GET /v1/wallet/ledger": () =>
      json(200, { items: [entry()], next_cursor: null }),
    ...overrides,
  });
}

function renderWallet(gender: "male" | "female") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "u1", gender });
  return render(
    <QueryClientProvider client={client}>
      <WalletScreen />
    </QueryClientProvider>,
  );
}

const section = (name: string) => screen.getByRole("region", { name });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubGlobal("IntersectionObserver", FakeObserver);
  FakeObserver.live.clear();
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("a man's wallet: the balance card (T-5.5)", () => {
  it("shows his balance in Velas, and Buy Velas opens the store sheet", async () => {
    routes();
    renderWallet("male");

    expect(
      await screen.findByRole("heading", { name: t("wallet.balance") }),
    ).toBeInTheDocument();
    expect(await screen.findByText("30")).toBeInTheDocument();
    expect(screen.getByText(t("wallet.unit.other"))).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: t("wallet.buy") }),
    );
    expect(useStoreSheet.getState().open).toBe(true);
  });

  it("says when the balance couldn't load, and tries again", async () => {
    let fail = true;
    routes({
      "GET /v1/wallet": () =>
        fail ? envelope(500, "INTERNAL") : json(200, { balance: 7 }),
    });
    renderWallet("male");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(t("wallet.balanceFailed"));
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(await screen.findByText("7")).toBeInTheDocument();
  });
});

describe("a man's wallet: what things cost (T-5.5)", () => {
  it("lists /prices' nine actions in its own order, then the two free knot rows", async () => {
    routes();
    renderWallet("male");

    const prices = await screen.findByRole("region", {
      name: t("wallet.prices"),
    });
    const rows = await within(prices).findAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      "Open a thread5 Velas",
      "Re-open an expired thread2 Velas",
      "Extend a thread by a day10 Velas",
      "First private message8 Velas",
      "Each private message after it2 Velas",
      "View private pictures1 Vela",
      "Listen to a voice note5 Velas",
      "Super Like5 Velas",
      "See one person who liked you20 Velas",
      "Tie the knotFree",
      "Messaging in a knotFree",
    ]);
  });

  it("has none of the prototype's prices that no longer exist", async () => {
    routes();
    renderWallet("male");

    const prices = await screen.findByRole("region", {
      name: t("wallet.prices"),
    });
    await within(prices).findAllByRole("listitem");
    expect(prices).not.toHaveTextContent(/wink|boost|call|gift|500|credit/i);
  });

  it("says when the prices couldn't load, and tries again", async () => {
    let fail = true;
    routes({
      "GET /v1/prices": () =>
        fail ? envelope(500, "INTERNAL") : json(200, { thread_open: 5 }),
    });
    renderWallet("male");

    const prices = section(t("wallet.prices"));
    const alert = await within(prices).findByRole("alert");
    expect(alert).toHaveTextContent(t("wallet.pricesFailed"));
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(
      await within(prices).findByText("Open a thread"),
    ).toBeInTheDocument();
  });
});

describe("priceRows", () => {
  it("leaves out an action /prices doesn't return: switched off", () => {
    const active = Object.fromEntries(
      Object.entries(PRICES).filter(([key]) => key !== "thread_extend"),
    );
    const keys = priceRows(active).map(({ key }) => key);
    expect(keys).toHaveLength(8);
    expect(keys).not.toContain("thread_extend");
  });

  it("shows an action it has no price words for by its history words, after the rest", () => {
    const rows = priceRows({ gift: 5, thread_open: 5 });
    expect(rows).toEqual([
      { key: "thread_open", label: "Open a thread", credits: 5 },
      { key: "gift", label: t("wallet.reason.gift"), credits: 5 },
    ]);
  });

  it("leaves out a key that isn't a ledger reason: it has no words at all", () => {
    expect(
      priceRows({ wink: 2, thread_open: 5 }).map(({ key }) => key),
    ).toEqual(["thread_open"]);
  });

  it("calls a price of 0 free", async () => {
    routes({ "GET /v1/prices": () => json(200, { super_like: 0 }) });
    renderWallet("male");

    const prices = await screen.findByRole("region", {
      name: t("wallet.prices"),
    });
    expect(await within(prices).findByText("Super Like")).toBeInTheDocument();
    expect(
      within(prices)
        .getAllByRole("listitem")
        .map((row) => row.textContent),
    ).toContain("Super LikeFree");
  });
});

describe("a man's wallet: his history (T-5.5)", () => {
  it("says each entry in words, when it happened, and the change, signed", async () => {
    routes({
      "GET /v1/wallet/ledger": () =>
        json(200, {
          items: [
            entry({ id: "e2", delta: -5, reason: "thread_open" }),
            entry({
              id: "e1",
              delta: 30,
              reason: "admin_grant",
              created_at: "2026-10-01T04:30:00Z",
            }),
          ],
          next_cursor: null,
        }),
    });
    renderWallet("male");

    const history = section(t("wallet.history"));
    const rows = await within(history).findAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      `Thread opened${entryTime.format(new Date("2026-10-05T09:12:00Z"))}−5`,
      `Added by Zephyrine${entryTime.format(new Date("2026-10-01T04:30:00Z"))}+30`,
    ]);
    expect(within(rows[0]!).getByText(/2026/)).toHaveAttribute(
      "datetime",
      "2026-10-05T09:12:00Z",
    );
  });

  it("loads the next page as the end scrolls into view, and stops at the last", async () => {
    let asked = 0;
    const api = routes({
      "GET /v1/wallet/ledger": () => {
        asked += 1;
        return asked === 1
          ? json(200, { items: [entry({ id: "a" })], next_cursor: "c2" })
          : json(200, { items: [entry({ id: "b" })], next_cursor: null });
      },
    });
    renderWallet("male");
    const history = section(t("wallet.history"));
    await within(history).findAllByRole("listitem");

    scrollToEnd();

    await waitFor(() =>
      expect(within(history).getAllByRole("listitem")).toHaveLength(2),
    );
    await waitFor(() => expect(FakeObserver.live.size).toBe(0));
    scrollToEnd();
    expect(
      api.sent().filter((request) => request === "GET /v1/wallet/ledger"),
    ).toHaveLength(2);
  });

  it("says when a later page fails, waits for Try again, then loads it", async () => {
    let asked = 0;
    routes({
      "GET /v1/wallet/ledger": () => {
        asked += 1;
        if (asked === 1) {
          return json(200, { items: [entry({ id: "a" })], next_cursor: "c2" });
        }
        return asked === 2
          ? envelope(500, "INTERNAL")
          : json(200, { items: [entry({ id: "b" })], next_cursor: null });
      },
    });
    renderWallet("male");
    const history = section(t("wallet.history"));
    await within(history).findAllByRole("listitem");

    scrollToEnd();
    const alert = await within(history).findByRole("alert");
    // A failed page doesn't ask again by itself.
    expect(FakeObserver.live.size).toBe(0);
    expect(asked).toBe(2);

    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );
    await waitFor(() =>
      expect(within(history).getAllByRole("listitem")).toHaveLength(2),
    );
    expect(within(history).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("says when there's nothing yet", async () => {
    routes({
      "GET /v1/wallet/ledger": () =>
        json(200, { items: [], next_cursor: null }),
    });
    renderWallet("male");

    const history = section(t("wallet.history"));
    expect(
      await within(history).findByRole("heading", {
        name: t("wallet.historyEmpty"),
      }),
    ).toBeInTheDocument();
  });

  it("says when the history couldn't load, and tries again", async () => {
    let fail = true;
    routes({
      "GET /v1/wallet/ledger": () =>
        fail
          ? envelope(500, "INTERNAL")
          : json(200, { items: [entry()], next_cursor: null }),
    });
    renderWallet("male");

    const history = section(t("wallet.history"));
    const alert = await within(history).findByRole("alert");
    expect(alert).toHaveTextContent(t("wallet.historyFailed"));
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(await within(history).findAllByRole("listitem")).toHaveLength(1);
  });

  it("marks each part busy while it loads", () => {
    const never = () => new Promise<Response>(() => {});
    routes({
      "GET /v1/wallet": never,
      "GET /v1/prices": never,
      "GET /v1/wallet/ledger": never,
    });
    renderWallet("male");

    expect(section(t("wallet.prices"))).toHaveAttribute("aria-busy", "true");
    expect(section(t("wallet.history"))).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });
});

describe("a man's wallet: refunds (T-5.5)", () => {
  it("links quietly to the refund policy, and offers no refund of its own", async () => {
    routes();
    renderWallet("male");
    await screen.findAllByRole("listitem");

    expect(
      screen.getByRole("link", { name: t("wallet.refunds") }),
    ).toHaveAttribute("href", "/refunds");
    expect(
      screen.queryByRole("button", { name: /refund/i }),
    ).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/refundable|7 days|unspent/i);
  });
});

describe("a woman's wallet (T-5.5)", () => {
  it("says everything is free, without calls, and asks the API for nothing", async () => {
    const api = fakeApi({});
    renderWallet("female");

    expect(
      screen.getByRole("heading", { name: t("wallet.womenTitle") }),
    ).toBeInTheDocument();
    expect(document.body).toHaveTextContent(t("wallet.womenBody"));
    expect(document.body).not.toHaveTextContent(/call/i);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    await waitFor(() => expect(api.sent()).toEqual([]));
  });
});
