import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, json } from "@/lib/testing/fakeApi";

import { useLedger, usePrices, useWallet, type LedgerEntry } from "./wallet";

function entry(id: string, delta = -5): LedgerEntry {
  return {
    id,
    delta,
    balance_after: 10,
    reason: "thread_open",
    created_at: "2026-10-05T09:12:00Z",
  };
}

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
  act(() => focusManager.setFocused(undefined));
});

describe("useWallet (T-5.5)", () => {
  it("reads the balance from GET /v1/wallet", async () => {
    const api = fakeApi({ "GET /v1/wallet": () => json(200, { balance: 12 }) });

    const { result } = renderHook(() => useWallet(), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual({ balance: 12 }));
    expect(api.sent()).toEqual(["GET /v1/wallet"]);
  });

  it("asks nothing while it isn't enabled: a woman's header", async () => {
    const api = fakeApi({});

    const { result } = renderHook(() => useWallet({ enabled: false }), {
      wrapper,
    });

    await act(() => Promise.resolve());
    expect(result.current.fetchStatus).toBe("idle");
    expect(api.sent()).toEqual([]);
  });

  it("asks again when the window regains focus, however fresh the balance", async () => {
    // Fresh for an hour: a focus refetch that waited for staleness would skip.
    client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 3_600_000 } },
    });
    let balance = 12;
    const api = fakeApi({ "GET /v1/wallet": () => json(200, { balance }) });
    const { result } = renderHook(() => useWallet(), { wrapper });
    await waitFor(() => expect(result.current.data?.balance).toBe(12));

    balance = 7;
    act(() => focusManager.setFocused(false));
    act(() => focusManager.setFocused(true));

    await waitFor(() => expect(result.current.data?.balance).toBe(7));
    expect(api.sent()).toEqual(["GET /v1/wallet", "GET /v1/wallet"]);
  });

  it("never asks on a timer: no polling until the socket (T-7.12)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = fakeApi({ "GET /v1/wallet": () => json(200, { balance: 12 }) });
    const { result } = renderHook(() => useWallet(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await vi.advanceTimersByTimeAsync(10 * 60_000);

    expect(api.sent()).toEqual(["GET /v1/wallet"]);
  });
});

describe("useLedger (T-5.5)", () => {
  it("pages by the API's cursor, and stops where next_cursor is null", async () => {
    // fakeApi keeps only the path; the cursor is in the query string.
    const cursors: Array<string | null> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        expect(url.pathname).toBe("/v1/wallet/ledger");
        const cursor = url.searchParams.get("cursor");
        cursors.push(cursor);
        return cursor === "c2"
          ? json(200, { items: [entry("e3")], next_cursor: null })
          : json(200, { items: [entry("e1"), entry("e2")], next_cursor: "c2" });
      }),
    );
    const { result } = renderHook(() => useLedger(), { wrapper });
    await waitFor(() => expect(result.current.hasNextPage).toBe(true));

    await act(() => result.current.fetchNextPage());

    await waitFor(() => expect(result.current.hasNextPage).toBe(false));
    expect(
      result.current.data?.pages.flatMap((page) => page.items.map((e) => e.id)),
    ).toEqual(["e1", "e2", "e3"]);
    // The first page sends no cursor at all, never "null".
    expect(cursors).toEqual([null, "c2"]);
  });
});

describe("usePrices (T-5.5)", () => {
  it("reads every active action's price from GET /v1/prices", async () => {
    fakeApi({
      "GET /v1/prices": () => json(200, { thread_open: 5, album_request: 1 }),
    });

    const { result } = renderHook(() => usePrices(), { wrapper });

    await waitFor(() =>
      expect(result.current.data).toEqual({ thread_open: 5, album_request: 1 }),
    );
  });
});
