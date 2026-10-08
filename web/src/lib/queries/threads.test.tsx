import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, json } from "@/lib/testing/fakeApi";

import { makeQueryClient } from "./QueryProvider";
import {
  useClearThreads,
  useExtendThread,
  useReopenThread,
  useRestoreThread,
  useThreads,
} from "./threads";
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

/** A client of its own, for T-7.10's hooks, retrying nothing. */
function freshWrapper() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  return Wrapper;
}

describe("the chats list's hooks (T-7.10)", () => {
  it("asks for a tier and filter, 50 a page, q only when it says something, then the next page by its cursor", async () => {
    const api = fakeApi({
      "GET /v1/threads": (call) =>
        json(200, {
          items: [],
          next_cursor: call.query.has("cursor") ? null : "c2",
        }),
    });
    const { result } = renderHook(() => useThreads("knots", "recent", ""), {
      wrapper: freshWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const first = api.calls[0]!.query;
    expect(Object.fromEntries(first)).toEqual({
      tier: "knots",
      filter: "recent",
      limit: "50",
    });

    await act(() => result.current.fetchNextPage());
    expect(api.calls[1]!.query.get("cursor")).toBe("c2");
  });

  it("asks nothing while it isn't enabled", async () => {
    const api = fakeApi({
      "GET /v1/threads": () => json(200, { items: [], next_cursor: null }),
    });
    renderHook(() => useThreads("threads", "all", "pri", false), {
      wrapper: freshWrapper(),
    });

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.calls).toHaveLength(0);
  });

  it("restores by DELETE, and clears several in one request", async () => {
    const api = fakeApi({
      "DELETE /v1/threads/t1/clear": () => json(204),
      "POST /v1/threads/clear": () => json(200, { cleared: 1 }),
    });
    const restore = renderHook(() => useRestoreThread(), {
      wrapper: freshWrapper(),
    });
    const many = renderHook(() => useClearThreads(), {
      wrapper: freshWrapper(),
    });

    await act(() => restore.result.current.mutateAsync("t1"));
    const answer = await act(() =>
      many.result.current.mutateAsync({ expired: true }),
    );

    expect(api.sent()).toEqual([
      "DELETE /v1/threads/t1/clear",
      "POST /v1/threads/clear",
    ]);
    expect(api.calls[1]!.body).toEqual({ expired: true });
    expect(answer).toEqual({ cleared: 1 });
  });
});
