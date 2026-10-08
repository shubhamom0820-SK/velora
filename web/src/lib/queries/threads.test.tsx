import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, json } from "@/lib/testing/fakeApi";

import { makeQueryClient } from "./QueryProvider";
import { useExtendThread, useReopenThread } from "./threads";
import { useWallet } from "./wallet";

const THREAD = {
  id: "7c1d6c3e-0000-4000-8000-000000000001",
  origin: "match",
  status: "active",
  other_user_id: "7c1d6c3e-0000-4000-8000-000000000002",
  expires_at: "2026-10-08T07:30:00Z",
  knotted_at: null,
  i_tied: false,
  last_message_at: null,
  created_at: "2026-10-08T06:30:00Z",
};

let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = makeQueryClient();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe.each([
  ["useReopenThread", useReopenThread, "reopen", 2],
  ["useExtendThread", useExtendThread, "extend", 10],
] as const)("%s (T-7.6)", (_, useHook, what, price) => {
  const path = `/v1/threads/${THREAD.id}/${what}`;

  it("sends the price it showed and the tap's key (P-56, D-077)", async () => {
    const api = fakeApi({ [`POST ${path}`]: () => json(200, THREAD) });
    const { result } = renderHook(() => useHook(), { wrapper });

    let got: unknown;
    await act(async () => {
      got = await result.current.mutateAsync({
        thread_id: THREAD.id,
        shown_price: price,
        key: "tap-0001",
      });
    });

    expect(api.sent()).toEqual([`POST ${path}`]);
    const [call] = api.calls;
    expect(call?.body).toEqual({ shown_price: price });
    expect(call?.headers.get("Idempotency-Key")).toBe("tap-0001");
    expect(got).toEqual(THREAD);
  });

  it("asks for the balance again when it settles: it spends Velas (T-5.5)", async () => {
    const api = fakeApi({
      "GET /v1/wallet": () => json(200, { balance: 12 }),
      [`POST ${path}`]: () => json(200, THREAD),
    });
    const { result } = renderHook(
      () => ({ wallet: useWallet(), buy: useHook() }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.wallet.data?.balance).toBe(12));

    await act(() =>
      result.current.buy.mutateAsync({
        thread_id: THREAD.id,
        shown_price: price,
        key: "tap-0001",
      }),
    );

    await waitFor(() =>
      expect(api.sent()).toEqual([
        "GET /v1/wallet",
        `POST ${path}`,
        "GET /v1/wallet",
      ]),
    );
  });
});
