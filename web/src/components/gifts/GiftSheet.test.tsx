import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { queryKeys } from "@/lib/queries/keys";
import {
  type Call,
  envelope,
  fakeApi,
  json,
  type Route,
} from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { GiftSheet, waitText } from "./GiftSheet";

function catalogue(freeLeft: number | null = 3) {
  return {
    gifts: [
      { id: "coffee", label: "Coffee", asset: "☕", credits: 5 },
      { id: "rose", label: "Rose", asset: "🌹", credits: 10 },
      { id: "chocolate", label: "Chocolate", asset: "🍫", credits: 15 },
      { id: "teddy", label: "Teddy", asset: "🧸", credits: 20 },
    ],
    free_sends_left: freeLeft,
    // Monday 12 October 2026, 00:00 IST (D-650).
    free_sends_reset_at: "2026-10-11T18:30:00Z",
  };
}

const SENT = {
  id: "s1",
  gift_id: "rose",
  recipient_id: "u2",
  credits_charged: 0,
  thread_id: null,
  created_at: "2026-10-09T10:00:00Z",
};

function routes(send: Route, freeLeft: number | null = 3) {
  return fakeApi({
    "GET /v1/gifts": () => json(200, catalogue(freeLeft)),
    "POST /v1/gifts/send": send,
  });
}

function renderSheet() {
  const client = makeQueryClient();
  client.setQueryData(queryKeys.me(), { id: "u1", gender: "male" });
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <GiftSheet recipientId="u2" name="Simran" onClose={onClose} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { onClose };
}

const sheet = () =>
  screen.getByRole("dialog", { name: t("gifts.title", { name: "Simran" }) });

async function choose(name: string) {
  await userEvent.click(await within(sheet()).findByRole("button", { name }));
}

function sendButton(gift: string, price: string) {
  return within(sheet()).getByRole("button", {
    name: t("gifts.send", { gift, price }),
  });
}

const posts = (calls: Call[]) => calls.filter((c) => c.method === "POST");
const keyOf = (call: Call | undefined) => call?.headers.get("Idempotency-Key");

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the gift sheet (T-8.10)", () => {
  it("shows the four gifts free while a free send is left, and sends price 0", async () => {
    const api = routes(() => json(200, SENT));
    const { onClose } = renderSheet();

    expect(
      await screen.findByText(t("gifts.freeLeft.other", { count: 3 })),
    ).toBeInTheDocument();
    for (const name of ["Coffee", "Rose", "Chocolate", "Teddy"]) {
      expect(
        within(sheet()).getByRole("button", { name: `${name}, Free` }),
      ).toBeInTheDocument();
    }
    expect(
      within(sheet()).getByRole("button", { name: t("gifts.choose") }),
    ).toBeDisabled();

    await choose("Rose, Free");
    await userEvent.click(sendButton("Rose", "Free"));

    expect(await screen.findByText("Rose sent to Simran")).toBeInTheDocument();
    expect(onClose).toHaveBeenCalled();
    const [post] = posts(api.calls);
    expect(post?.body).toEqual({
      recipient_id: "u2",
      gift_id: "rose",
      shown_price: 0,
    });
    expect(keyOf(post)).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it("says 1 free send in the singular", async () => {
    routes(() => json(200, SENT), 1);
    renderSheet();

    expect(
      await screen.findByText("1 free send left this week"),
    ).toBeInTheDocument();
  });

  it("past the week's free sends, shows and sends each gift's own price", async () => {
    const api = routes(() => json(200, { ...SENT, credits_charged: 10 }), 0);
    renderSheet();

    expect(
      await screen.findByText(
        "No free sends left this week. They come back Monday, 12 October.",
      ),
    ).toBeInTheDocument();
    expect(
      within(sheet()).getByRole("button", { name: "Coffee, 5 Velas" }),
    ).toBeInTheDocument();
    await choose("Rose, 10 Velas");
    await userEvent.click(sendButton("Rose", "10 Velas"));

    await waitFor(() => expect(posts(api.calls)).toHaveLength(1));
    expect(posts(api.calls)[0]?.body).toMatchObject({ shown_price: 10 });
  });

  it("asks for the free sends again after a send", async () => {
    const api = routes(() => json(200, SENT));
    renderSheet();

    await choose("Rose, Free");
    await userEvent.click(sendButton("Rose", "Free"));

    await waitFor(() =>
      expect(api.sent().filter((s) => s === "GET /v1/gifts")).toHaveLength(2),
    );
  });

  it("sends once however fast it is tapped twice", async () => {
    let answer: (response: Response) => void = () => {};
    const api = routes(
      () => new Promise<Response>((resolve) => (answer = resolve)),
    );
    renderSheet();

    await choose("Rose, Free");
    const button = sendButton("Rose", "Free");
    await userEvent.click(button);
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-busy", "true");
    answer(json(200, SENT));

    expect(await screen.findByText("Rose sent to Simran")).toBeInTheDocument();
    expect(posts(api.calls)).toHaveLength(1);
  });

  it("sends the same key again when a send got no answer", async () => {
    let fail = true;
    const api = routes(() => {
      if (fail) throw new TypeError("Failed to fetch");
      return json(200, SENT);
    });
    renderSheet();

    await choose("Rose, Free");
    await userEvent.click(sendButton("Rose", "Free"));
    expect(await screen.findByText(t("gifts.failed"))).toBeInTheDocument();
    fail = false;
    await userEvent.click(sendButton("Rose", "Free"));

    expect(await screen.findByText("Rose sent to Simran")).toBeInTheDocument();
    const [first, second] = posts(api.calls);
    expect(keyOf(second)).toBe(keyOf(first));
  });

  it("GIFT_COOLDOWN: says when, holds that gift, and another goes with a new key", async () => {
    const api = routes((call) =>
      (call.body as { gift_id: string }).gift_id === "rose"
        ? envelope(429, "GIFT_COOLDOWN", { retry_after_s: 18_701 })
        : json(200, { ...SENT, gift_id: "coffee" }),
    );
    renderSheet();

    await choose("Rose, Free");
    await userEvent.click(sendButton("Rose", "Free"));

    expect(
      await screen.findByText(
        "You sent Simran a Rose recently. You can send another in 5h 12m, or choose a different gift now.",
      ),
    ).toBeInTheDocument();
    expect(sendButton("Rose", "Free")).toBeDisabled();

    await choose("Coffee, Free");
    await userEvent.click(sendButton("Coffee", "Free"));
    expect(
      await screen.findByText("Coffee sent to Simran"),
    ).toBeInTheDocument();
    const [rose, coffee] = posts(api.calls);
    expect(keyOf(coffee)).not.toBe(keyOf(rose));
  });

  it("PRICE_CHANGED: shows the new price, sends nothing more until tapped, then sends it", async () => {
    let refused = false;
    const api = routes(() => {
      if (refused) return json(200, { ...SENT, credits_charged: 10 });
      refused = true;
      return envelope(409, "PRICE_CHANGED", { price: 10 });
    });
    renderSheet();

    await choose("Rose, Free");
    await userEvent.click(sendButton("Rose", "Free"));

    expect(
      await screen.findByText("The price changed. It's 10 Velas now."),
    ).toBeInTheDocument();
    expect(
      within(sheet()).getByRole("button", { name: "Rose, 10 Velas" }),
    ).toBeInTheDocument();
    expect(posts(api.calls)).toHaveLength(1);

    await userEvent.click(sendButton("Rose", "10 Velas"));
    await waitFor(() => expect(posts(api.calls)).toHaveLength(2));
    const [first, second] = posts(api.calls);
    expect(second?.body).toMatchObject({ gift_id: "rose", shown_price: 10 });
    expect(keyOf(second)).not.toBe(keyOf(first));
  });

  it("PRICE_CHANGED to 0: says it is free now", async () => {
    routes(() => envelope(409, "PRICE_CHANGED", { price: 0 }), 0);
    renderSheet();

    await choose("Rose, 10 Velas");
    await userEvent.click(sendButton("Rose", "10 Velas"));

    expect(await screen.findByText(t("gifts.nowFree"))).toBeInTheDocument();
    expect(sendButton("Rose", "Free")).toBeEnabled();
  });

  it("INSUFFICIENT_CREDITS: opens the store and makes way for it", async () => {
    routes(() => envelope(402, "INSUFFICIENT_CREDITS"), 0);
    const { onClose } = renderSheet();

    await choose("Teddy, 20 Velas");
    await userEvent.click(sendButton("Teddy", "20 Velas"));

    await waitFor(() => expect(useStoreSheet.getState().open).toBe(true));
    expect(onClose).toHaveBeenCalled();
  });

  it.each([
    [404, "NOT_FOUND"],
    [422, "NOT_ALLOWED"],
  ])("%i %s: says she can't receive gifts right now", async (status, code) => {
    routes(() => envelope(status, code));
    const { onClose } = renderSheet();

    await choose("Rose, Free");
    await userEvent.click(sendButton("Rose", "Free"));

    expect(
      await screen.findByText(t("gifts.unavailable", { name: "Simran" })),
    ).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows a skeleton while loading, and a retry when the gifts don't load", async () => {
    let fail = true;
    fakeApi({
      "GET /v1/gifts": () =>
        // A 4xx, which the query client never retries (QueryProvider).
        fail ? envelope(429, "RATE_LIMITED") : json(200, catalogue()),
    });
    renderSheet();

    expect(sheet().querySelector("[aria-busy]")).not.toBeNull();
    const alert = await within(sheet()).findByRole("alert");
    expect(alert).toHaveTextContent(t("gifts.loadFailed"));
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(
      await within(sheet()).findByRole("button", { name: "Rose, Free" }),
    ).toBeInTheDocument();
  });
});

describe("waitText", () => {
  it.each([
    [1, "1m"],
    [60, "1m"],
    [61, "2m"],
    [3_600, "1h 0m"],
    [18_701, "5h 12m"],
    [86_400, "24h 0m"],
  ])("%i s reads %s, rounded up", (seconds, text) => {
    expect(waitText(seconds)).toBe(text);
  });
});
