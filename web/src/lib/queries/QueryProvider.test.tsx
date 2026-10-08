import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { fakeApi, json } from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { makeQueryClient, shouldRetry } from "./QueryProvider";
import { useLedger, usePrices, useWallet } from "./wallet";

function apiError(status: number) {
  return new ApiError({ code: "X", message: "x", status });
}

describe("shouldRetry", () => {
  it.each([400, 401, 402, 404, 409, 422, 429])(
    "never retries a %i: it is the API's answer",
    (status) => {
      expect(shouldRetry(0, apiError(status))).toBe(false);
    },
  );

  it.each([
    ["a 500", apiError(500)],
    ["a 503", apiError(503)],
    ["a network failure", new TypeError("Failed to fetch")],
  ])("retries %s twice, then stops", (_, error) => {
    expect(shouldRetry(0, error)).toBe(true);
    expect(shouldRetry(1, error)).toBe(true);
    expect(shouldRetry(2, error)).toBe(false);
  });
});

describe("the mutation cache (T-5.5)", () => {
  let client: QueryClient;
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }

  const refused = (code: string, status: number) =>
    new ApiError({ code, message: code, status });

  /** The wallet's two queries, mounted, plus one mutation to run. */
  async function mountWallet(
    options: Parameters<typeof useMutation<unknown, Error, void>>[0],
  ) {
    const api = fakeApi({
      "GET /v1/wallet": () => json(200, { balance: 3 }),
      "GET /v1/wallet/ledger": () =>
        json(200, { items: [], next_cursor: null }),
    });
    const { result } = renderHook(
      () => ({
        wallet: useWallet(),
        ledger: useLedger(),
        mutation: useMutation(options),
      }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.wallet.isSuccess).toBe(true));
    await waitFor(() => expect(result.current.ledger.isSuccess).toBe(true));
    return { api, result };
  }

  const walletReads = (sent: string[]) =>
    sent.filter((request) => request.startsWith("GET /v1/wallet"));

  /** Lets a refetch that shouldn't happen have its chance to. */
  const settle = () =>
    act(() => new Promise((resolve) => setTimeout(resolve, 50)));

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
    client = makeQueryClient();
    useStoreSheet.setState({ open: false });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    useStoreSheet.setState({ open: false });
  });

  it("opens the store sheet when a mutation is refused with INSUFFICIENT_CREDITS, and asks for the balance again", async () => {
    const { api, result } = await mountWallet({
      mutationFn: () => Promise.reject(refused("INSUFFICIENT_CREDITS", 402)),
    });

    await act(() => result.current.mutation.mutateAsync().catch(() => {}));

    expect(useStoreSheet.getState().open).toBe(true);
    await waitFor(() =>
      expect(walletReads(api.sent())).toEqual([
        "GET /v1/wallet",
        "GET /v1/wallet/ledger",
        "GET /v1/wallet",
        "GET /v1/wallet/ledger",
      ]),
    );
  });

  it.each([
    ["another refusal", refused("NOT_ALLOWED", 422)],
    ["a 402 with another code", refused("PAYMENT_REQUIRED", 402)],
    ["a network failure", new TypeError("Failed to fetch")],
  ])("leaves the store sheet shut for %s", async (_, error) => {
    const { api, result } = await mountWallet({
      mutationFn: () => Promise.reject(error),
    });

    await act(() => result.current.mutation.mutateAsync().catch(() => {}));

    await settle();
    expect(useStoreSheet.getState().open).toBe(false);
    expect(walletReads(api.sent())).toHaveLength(2);
  });

  it("never opens it from a query, whatever the query is refused with", async () => {
    fakeApi({});
    const { result } = renderHook(
      () =>
        useQuery({
          queryKey: ["anything"],
          queryFn: () => Promise.reject(refused("INSUFFICIENT_CREDITS", 402)),
          retry: false,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(useStoreSheet.getState().open).toBe(false);
  });

  it.each([
    ["succeeds", () => Promise.resolve("done")],
    ["fails", () => Promise.reject(refused("INTERNAL", 500))],
  ])(
    "asks for the balance and history again when a mutation marked touchesWallet %s",
    async (_, mutationFn) => {
      const { api, result } = await mountWallet({
        mutationFn,
        meta: { touchesWallet: true },
      });

      await act(() => result.current.mutation.mutateAsync().catch(() => {}));

      await waitFor(() => expect(walletReads(api.sent())).toHaveLength(4));
      expect(useStoreSheet.getState().open).toBe(false);
    },
  );

  it.each([
    ["PRICE_CHANGED", refused("PRICE_CHANGED", 409), 2],
    ["another refusal", refused("NOT_ALLOWED", 422), 1],
  ])(
    "asks for /prices again when a mutation is refused with %s (P-56), and never opens the store",
    async (_, error, reads) => {
      const api = fakeApi({
        "GET /v1/prices": () => json(200, { super_like: 6 }),
      });
      const { result } = renderHook(
        () => ({
          prices: usePrices(),
          mutation: useMutation({ mutationFn: () => Promise.reject(error) }),
        }),
        { wrapper },
      );
      await waitFor(() => expect(result.current.prices.isSuccess).toBe(true));

      await act(() => result.current.mutation.mutateAsync().catch(() => {}));

      await settle();
      expect(api.sent().filter((r) => r === "GET /v1/prices")).toHaveLength(
        reads,
      );
      expect(useStoreSheet.getState().open).toBe(false);
    },
  );

  it("leaves the wallet alone after a mutation that isn't marked", async () => {
    const { api, result } = await mountWallet({
      mutationFn: () => Promise.resolve("done"),
    });

    await act(() => result.current.mutation.mutateAsync());

    await settle();
    expect(walletReads(api.sent())).toHaveLength(2);
  });
});
