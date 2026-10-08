import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { en } from "@/i18n/en";
import { t, type MessageKey } from "@/i18n/t";
import { FAKE_KEY_ID } from "@/lib/checkout-path";
import { queryKeys } from "@/lib/queries/keys";
import type { Order, Pack } from "@/lib/queries/store";
import { openRazorpay, type CheckoutCallbacks } from "@/lib/razorpay";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { resetSession, useSession } from "@/store/session";
import { useStoreSheet } from "@/store/store-sheet";

import { StoreSheet } from "./StoreSheet";

vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));
vi.mock("@/lib/razorpay", async (original) => ({
  ...(await original<typeof import("@/lib/razorpay")>()),
  openRazorpay: vi.fn(),
}));

/** D-099's four packs with D-231's first-purchase bonus, as `GET /packs` sends them. */
const PACKS: Pack[] = [
  { id: "p30", credits: 30, price_paise: 150_000, bonus_credits: 6 },
  { id: "p100", credits: 100, price_paise: 450_000, bonus_credits: 20 },
  { id: "p250", credits: 250, price_paise: 600_000, bonus_credits: 50 },
  { id: "p450", credits: 450, price_paise: 1_000_000, bonus_credits: 90 },
];

const PAYMENT = "5b0d5f8e-2c4a-4d0e-9a0b-1f1e1d1c1b1a";

const ORDER: Order = {
  payment_id: PAYMENT,
  order_id: "order_fake_1",
  key_id: FAKE_KEY_ID,
  amount_paise: 150_000,
};

const status = (value: string) =>
  json(200, { status: value, credits: 30, bonus_credits: 6 });

function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/packs": () => json(200, PACKS),
    "GET /v1/prices": () => json(200, { thread_open: 5 }),
    "POST /v1/payments/orders": () => json(200, ORDER),
    [`GET /v1/payments/${PAYMENT}`]: () => status("created"),
    ...overrides,
  });
}

function renderStore(gender: "male" | "female" = "male") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "u1", gender });
  client.setQueryData(queryKeys.wallet(), { balance: 5 });
  const view = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <StoreSheet />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { client, ...view };
}

const open = () => act(() => useStoreSheet.getState().show());
const sheet = (title: MessageKey) =>
  screen.findByRole("dialog", { name: t(title) });
const button = (name: string | RegExp) => screen.getByRole("button", { name });

/** The pack row a man taps: its button, found by its Velas. */
async function tapPack(velas: string) {
  const row = await screen.findByRole("button", {
    name: new RegExp(`^${velas}`),
  });
  await userEvent.click(row);
}

const count = (api: { sent: () => string[] }, request: string) =>
  api.sent().filter((sent) => sent === request).length;

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("CHECKOUT_PATH", "standin");
  useStoreSheet.setState({ open: false });
  vi.mocked(openRazorpay).mockReset();
});

afterEach(() => {
  resetSession();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the store sheet opens and closes as T-5.5 left it", () => {
  it("is shut until something opens it, and asks for nothing", () => {
    const api = routes();
    renderStore();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.sent()).toEqual([]);
  });

  it("closes with its ✕", async () => {
    routes();
    renderStore();
    open();

    await userEvent.click(
      within(await sheet("wallet.store.title")).getByRole("button", {
        name: t("ui.close"),
      }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(useStoreSheet.getState().open).toBe(false);
  });

  it("closes when the PIN lock goes up, and stays shut after unlocking", async () => {
    routes();
    renderStore();
    open();
    await sheet("wallet.store.title");

    act(() => useSession.getState().setLocked(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(useStoreSheet.getState().open).toBe(false);

    act(() => useSession.getState().setLocked(false));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes when the app's routes go away, so a sign-out doesn't carry it over", () => {
    routes();
    const { unmount } = renderStore();
    open();

    unmount();

    expect(useStoreSheet.getState().open).toBe(false);
  });
});

describe("a woman never sees the store (D-076)", () => {
  it("opened anyway, nothing shows, and her browser never asks for packs", async () => {
    const api = routes();
    renderStore("female");
    open();

    await act(async () => {});
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.sent()).not.toContain("GET /v1/packs");
  });
});

describe("the packs, from the API (T-8.7)", () => {
  it("lists the man's packs, with Best value and the first-purchase banner", async () => {
    routes();
    renderStore();
    open();

    const store = await sheet("wallet.store.title");
    expect(await within(store).findAllByRole("listitem")).toHaveLength(4);
    expect(store).toHaveTextContent(t("wallet.store.firstPurchase"));
    expect(store).toHaveTextContent(t("wallet.store.bestValue"));
    expect(store).not.toHaveTextContent(/popular/i);
    expect(
      within(store).getByRole("link", { name: t("wallet.store.refunds") }),
    ).toHaveAttribute("href", "/refunds");
  });

  it("shows it is loading while the packs are on their way", async () => {
    routes({ "GET /v1/packs": () => new Promise<Response>(() => {}) });
    renderStore();
    open();

    const store = await sheet("wallet.store.title");
    expect(
      within(store).getByLabelText(t("wallet.store.loading")),
    ).toHaveAttribute("aria-busy", "true");
  });

  it("says when the packs couldn't load, and tries again", async () => {
    let fail = true;
    routes({
      "GET /v1/packs": () =>
        fail ? envelope(500, "INTERNAL") : json(200, PACKS),
    });
    renderStore();
    open();

    const alert = await within(await sheet("wallet.store.title")).findByRole(
      "alert",
    );
    expect(alert).toHaveTextContent(t("wallet.store.failed"));
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(await screen.findAllByRole("listitem")).toHaveLength(4);
  });

  it("says so when there is nothing to buy", async () => {
    routes({ "GET /v1/packs": () => json(200, []) });
    renderStore();
    open();

    expect(
      await within(await sheet("wallet.store.title")).findByText(
        t("wallet.store.emptyTitle"),
      ),
    ).toBeInTheDocument();
  });
});

describe("buying a pack, on the stand-in (D-761)", () => {
  it("orders the pack by its id alone, under a fresh Idempotency-Key", async () => {
    const api = routes();
    renderStore();
    open();

    await tapPack("30 Velas");
    await sheet("wallet.store.standin.title");

    const order = api.calls.find((call) => call.path === "/v1/payments/orders");
    expect(order?.body).toEqual({ pack_id: "p30" });
    expect(order?.headers.get("Idempotency-Key")).toMatch(
      /^[A-Za-z0-9_-]{8,64}$/,
    );
  });

  it("paid: polls until the webhook lands, then says how many Velas came, and refreshes the balance and the packs", async () => {
    let polls = 0;
    const api = routes({
      [`GET /v1/payments/${PAYMENT}`]: () =>
        ++polls < 3 ? status("created") : status("paid"),
    });
    const { client } = renderStore();
    open();

    await tapPack("30 Velas");
    await sheet("wallet.store.standin.title");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await userEvent.click(button(t("wallet.store.standin.pay")));
    await sheet("wallet.store.confirming.title");
    await act(() => vi.advanceTimersByTimeAsync(3_000));

    expect(
      await screen.findByText(t("wallet.store.paid", { velas: "36 Velas" })),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(client.getQueryState(queryKeys.wallet())?.isInvalidated).toBe(true);
    expect(count(api, `GET /v1/payments/${PAYMENT}`)).toBe(3);
    // The bonus is gone after a first purchase: the packs are asked again.
    await waitFor(() => expect(count(api, "GET /v1/packs")).toBe(2));
  });

  it("asks every 1.5 s, and stops at 60 s with 'still confirming', where Check again asks again", async () => {
    const api = routes();
    renderStore();
    open();

    await tapPack("30 Velas");
    await sheet("wallet.store.standin.title");
    vi.useFakeTimers({ shouldAdvanceTime: false });
    await act(async () => {
      button(t("wallet.store.standin.pay")).click();
    });
    await act(() => vi.advanceTimersByTimeAsync(59_000));
    expect(screen.getByRole("dialog")).toHaveAccessibleName(
      t("wallet.store.confirming.title"),
    );
    // The first at once, then one every 1.5 s: 0, 1.5 … 58.5 s.
    expect(count(api, `GET /v1/payments/${PAYMENT}`)).toBe(40);

    await act(() => vi.advanceTimersByTimeAsync(1_000));
    expect(screen.getByRole("dialog")).toHaveAccessibleName(
      t("wallet.store.waiting.title"),
    );
    // The 60 s mark itself may or may not get its ask in first; none after.
    const asked = count(api, `GET /v1/payments/${PAYMENT}`);
    expect(asked).toBeLessThanOrEqual(41);
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(count(api, `GET /v1/payments/${PAYMENT}`)).toBe(asked);

    await act(async () => {
      button(t("wallet.store.waiting.check")).click();
    });
    await act(() => vi.advanceTimersByTimeAsync(10));
    expect(count(api, `GET /v1/payments/${PAYMENT}`)).toBe(asked + 1);
    expect(screen.getByRole("dialog")).toHaveAccessibleName(
      t("wallet.store.confirming.title"),
    );
  });

  it("a failed attempt doesn't end the wait: the same order can still be captured (T-8.2)", async () => {
    let polls = 0;
    routes({
      [`GET /v1/payments/${PAYMENT}`]: () =>
        ++polls < 3 ? status("failed") : status("paid"),
    });
    renderStore();
    open();

    await tapPack("30 Velas");
    await sheet("wallet.store.standin.title");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await userEvent.click(button(t("wallet.store.standin.pay")));
    await act(() => vi.advanceTimersByTimeAsync(3_000));

    expect(
      await screen.findByText(t("wallet.store.paid", { velas: "36 Velas" })),
    ).toBeInTheDocument();
    expect(screen.queryByText(t("wallet.store.notPaid.title"))).toBeNull();
  });

  it("closed without paying: 'didn't go through', and Try again reopens the same order, never a second", async () => {
    const api = routes();
    renderStore();
    open();

    await tapPack("30 Velas");
    await userEvent.click(button(t("wallet.store.standin.close")));
    await sheet("wallet.store.notPaid.title");
    await userEvent.click(button(t("wallet.store.notPaid.retry")));

    await sheet("wallet.store.standin.title");
    expect(count(api, "POST /v1/payments/orders")).toBe(1);
  });

  it("'Choose another pack' goes back to the packs", async () => {
    routes();
    renderStore();
    open();

    await tapPack("30 Velas");
    await userEvent.click(button(t("wallet.store.standin.close")));
    await userEvent.click(button(t("wallet.store.notPaid.packs")));

    expect(
      await within(await sheet("wallet.store.title")).findAllByRole("listitem"),
    ).toHaveLength(4);
  });

  it("the claim from 'didn't go through' names this payment", async () => {
    const api = routes({
      "POST /v1/refund-requests": () =>
        json(201, {
          id: "c1",
          payment_id: PAYMENT,
          reason: "missing_velas",
          status: "open",
          created_at: "2026-10-09T10:00:00Z",
        }),
    });
    renderStore();
    open();

    await tapPack("30 Velas");
    await userEvent.click(button(t("wallet.store.standin.close")));
    await userEvent.click(button(t("wallet.store.claim.open")));
    await sheet("wallet.store.claim.open");
    await userEvent.click(
      screen.getByRole("radio", {
        name: t("wallet.store.claim.missing_velas"),
      }),
    );
    await userEvent.click(button(t("wallet.store.claim.send")));

    expect(
      await screen.findByText(t("wallet.store.claim.sentTitle")),
    ).toBeInTheDocument();
    expect(
      api.calls.find((call) => call.path === "/v1/refund-requests")?.body,
    ).toEqual({ payment_id: PAYMENT, reason: "missing_velas" });
  });
});

describe("an order that can't open a window: nothing was charged", () => {
  it("a price other than the one shown: no window, the packs asked again", async () => {
    const api = routes({
      "POST /v1/payments/orders": () =>
        json(200, { ...ORDER, amount_paise: 160_000 }),
    });
    renderStore();
    open();

    await tapPack("30 Velas");

    const store = await sheet("wallet.store.title");
    expect(await within(store).findByRole("alert")).toHaveTextContent(
      t("wallet.store.priceChanged"),
    );
    expect(screen.queryByText(t("wallet.store.standin.title"))).toBeNull();
    await waitFor(() => expect(count(api, "GET /v1/packs")).toBe(2));
  });

  it.each<[string, Route, MessageKey, number]>([
    ["NOT_FOUND", () => envelope(404, "NOT_FOUND"), "wallet.store.packGone", 2],
    [
      "PROVIDER_UNAVAILABLE",
      () => envelope(503, "PROVIDER_UNAVAILABLE"),
      "wallet.store.unavailable",
      1,
    ],
    [
      "RATE_LIMITED",
      () => envelope(429, "RATE_LIMITED"),
      "wallet.store.tooMany",
      1,
    ],
    ["a 500", () => envelope(500, "INTERNAL"), "wallet.store.orderFailed", 1],
  ])("refused with %s, it says so", async (_code, route, words, packsAsked) => {
    const api = routes({ "POST /v1/payments/orders": route });
    renderStore();
    open();

    await tapPack("30 Velas");

    expect(
      await within(await sheet("wallet.store.title")).findByRole("alert"),
    ).toHaveTextContent(t(words));
    await waitFor(() => expect(count(api, "GET /v1/packs")).toBe(packsAsked));
  });

  it("a Razorpay build never opens the stand-in, even for the fake's order", async () => {
    vi.stubEnv("CHECKOUT_PATH", "razorpay");
    routes();
    renderStore();
    open();

    await tapPack("30 Velas");

    expect(
      await within(await sheet("wallet.store.title")).findByRole("alert"),
    ).toHaveTextContent(t("wallet.store.notHere"));
    expect(openRazorpay).not.toHaveBeenCalled();
  });

  it("a build with no checkout path opens nothing", async () => {
    vi.stubEnv("CHECKOUT_PATH", "");
    routes();
    renderStore();
    open();

    await tapPack("30 Velas");

    expect(
      await within(await sheet("wallet.store.title")).findByRole("alert"),
    ).toHaveTextContent(t("wallet.store.notHere"));
  });

  it("an order that lands after the sheet closed is ignored", async () => {
    let answer: (response: Response) => void = () => {};
    routes({
      "POST /v1/payments/orders": () =>
        new Promise<Response>((resolve) => {
          answer = resolve;
        }),
    });
    renderStore();
    open();

    await tapPack("30 Velas");
    act(() => useStoreSheet.getState().hide());
    await act(async () => answer(json(200, ORDER)));
    open();

    expect(await sheet("wallet.store.title")).toBeInTheDocument();
    expect(screen.queryByText(t("wallet.store.standin.body"))).toBeNull();
  });
});

describe("buying a pack, in Razorpay's window", () => {
  const REAL: Order = {
    ...ORDER,
    key_id: "rzp_test_aaaaaaaa",
    order_id: "order_Real",
  };
  let callbacks: CheckoutCallbacks | null = null;

  beforeEach(() => {
    vi.stubEnv("CHECKOUT_PATH", "razorpay");
    callbacks = null;
    vi.mocked(openRazorpay).mockImplementation(async (_order, given) => {
      callbacks = given;
    });
  });

  it("opens on the API's order, and this sheet steps aside while it's up", async () => {
    routes({ "POST /v1/payments/orders": () => json(200, REAL) });
    renderStore();
    open();

    await tapPack("30 Velas");

    await waitFor(() => expect(openRazorpay).toHaveBeenCalledTimes(1));
    expect(vi.mocked(openRazorpay).mock.calls[0]?.[0]).toEqual({
      keyId: "rzp_test_aaaaaaaa",
      orderId: "order_Real",
      amountPaise: 150_000,
      name: "Zephyrine",
      description: "30 Velas",
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("finished: the store waits for the webhook", async () => {
    routes({ "POST /v1/payments/orders": () => json(200, REAL) });
    renderStore();
    open();

    await tapPack("30 Velas");
    await waitFor(() => expect(callbacks).not.toBeNull());
    act(() => callbacks?.onPaid());

    expect(await sheet("wallet.store.confirming.title")).toBeInTheDocument();
  });

  it("closed: 'didn't go through', and Try again opens the same order again", async () => {
    const api = routes({ "POST /v1/payments/orders": () => json(200, REAL) });
    renderStore();
    open();

    await tapPack("30 Velas");
    await waitFor(() => expect(callbacks).not.toBeNull());
    act(() => callbacks?.onDismiss());
    await sheet("wallet.store.notPaid.title");
    await userEvent.click(button(t("wallet.store.notPaid.retry")));

    await waitFor(() => expect(openRazorpay).toHaveBeenCalledTimes(2));
    expect(vi.mocked(openRazorpay).mock.calls[1]?.[0].orderId).toBe(
      "order_Real",
    );
    expect(count(api, "POST /v1/payments/orders")).toBe(1);
  });

  it("a window that won't load says so; nothing was charged", async () => {
    vi.mocked(openRazorpay).mockRejectedValue(new Error("no script"));
    routes({ "POST /v1/payments/orders": () => json(200, REAL) });
    renderStore();
    open();

    await tapPack("30 Velas");

    expect(
      await within(await sheet("wallet.store.title")).findByRole("alert"),
    ).toHaveTextContent(t("wallet.store.windowFailed"));
  });
});

/** Every string under `en.wallet.store`, with its key. */
function storeStrings(): [string, string][] {
  const out: [string, string][] = [];
  const walk = (node: unknown, path: string) => {
    if (typeof node === "string") out.push([path, node]);
    else if (node && typeof node === "object")
      for (const [key, value] of Object.entries(node))
        walk(value, `${path}.${key}`);
  };
  walk(en.wallet.store, "wallet.store");
  return out;
}

describe("the store's words (D-450, D-482, D-760)", () => {
  it('never "GST", in any case, while Velora is unregistered', () => {
    const strings = storeStrings();
    expect(strings.length).toBeGreaterThan(20);
    expect(strings.filter(([, text]) => /gst/i.test(text))).toEqual([]);
  });

  it('never "Most popular": nobody has bought anything at launch (P-660)', () => {
    expect(storeStrings().filter(([, text]) => /popular/i.test(text))).toEqual(
      [],
    );
  });
});
