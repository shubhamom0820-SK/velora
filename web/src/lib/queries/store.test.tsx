import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, json } from "@/lib/testing/fakeApi";

import { queryKeys } from "./keys";
import { makeQueryClient } from "./QueryProvider";
import {
  POLL_EVERY_MS,
  POLL_FOR_MS,
  useCreateOrder,
  usePacks,
  usePaymentWait,
} from "./store";

const PAYMENT = "5b0d5f8e-2c4a-4d0e-9a0b-1f1e1d1c1b1a";

let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the plan's numbers (T-8.7's line)", () => {
  it("polls every 1.5 s, for 60 s at most", () => {
    expect(POLL_EVERY_MS).toBe(1_500);
    expect(POLL_FOR_MS).toBe(60_000);
  });
});

describe("usePacks", () => {
  it("asks nothing while it isn't enabled: a woman's browser never asks (D-076)", async () => {
    const api = fakeApi({});

    const { result } = renderHook(() => usePacks({ enabled: false }), {
      wrapper,
    });

    await act(() => Promise.resolve());
    expect(result.current.fetchStatus).toBe("idle");
    expect(api.sent()).toEqual([]);
  });
});

describe("useCreateOrder", () => {
  it("sends the pack's id alone under the Idempotency-Key, and is marked touchesWallet", async () => {
    client = makeQueryClient();
    client.setQueryData(queryKeys.wallet(), { balance: 5 });
    const api = fakeApi({
      "POST /v1/payments/orders": () =>
        json(200, {
          payment_id: PAYMENT,
          order_id: "order_fake_1",
          key_id: "rzp_fake_local_only",
          amount_paise: 150_000,
        }),
    });

    const { result } = renderHook(() => useCreateOrder(), { wrapper });
    await act(() =>
      result.current.mutateAsync({ packId: "p30", key: "aaaaaaaa" }),
    );

    expect(api.calls[0]?.body).toEqual({ pack_id: "p30" });
    expect(api.calls[0]?.headers.get("Idempotency-Key")).toBe("aaaaaaaa");
    expect(client.getMutationCache().getAll()[0]?.meta).toEqual({
      touchesWallet: true,
    });
    expect(client.getQueryState(queryKeys.wallet())?.isInvalidated).toBe(true);
  });
});

describe("usePaymentWait", () => {
  it("asks nothing without a payment", async () => {
    const api = fakeApi({});

    const { result } = renderHook(() => usePaymentWait(null), { wrapper });

    await act(() => Promise.resolve());
    expect(result.current).toEqual({ state: "waiting" });
    expect(api.sent()).toEqual([]);
  });

  it("paid: the Velas with the bonus, and the balance and the packs asked again", async () => {
    client.setQueryData(queryKeys.wallet(), { balance: 5 });
    client.setQueryData(queryKeys.walletLedger(), {
      pages: [],
      pageParams: [],
    });
    client.setQueryData(queryKeys.packs(), []);
    fakeApi({
      [`GET /v1/payments/${PAYMENT}`]: () =>
        json(200, { status: "paid", credits: 30, bonus_credits: 6 }),
    });

    const { result } = renderHook(() => usePaymentWait(PAYMENT), { wrapper });

    await waitFor(() =>
      expect(result.current).toEqual({ state: "paid", velas: 36 }),
    );
    for (const key of [
      queryKeys.wallet(),
      queryKeys.walletLedger(),
      queryKeys.packs(),
    ]) {
      expect(client.getQueryState(key)?.isInvalidated).toBe(true);
    }
  });

  it("stops asking once paid", async () => {
    vi.useFakeTimers();
    const api = fakeApi({
      [`GET /v1/payments/${PAYMENT}`]: () =>
        json(200, { status: "paid", credits: 30, bonus_credits: 0 }),
    });

    renderHook(() => usePaymentWait(PAYMENT), { wrapper });
    await act(() => vi.advanceTimersByTimeAsync(10_000));

    expect(api.sent()).toHaveLength(1);
  });
});
