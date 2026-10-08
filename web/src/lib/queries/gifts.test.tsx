import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { useSendGift } from "./gifts";
import { queryKeys } from "./keys";
import { makeQueryClient } from "./QueryProvider";

function wrapper() {
  const client = makeQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  return { client, Wrapper };
}

const VARIABLES = {
  recipient_id: "u2",
  gift_id: "rose",
  shown_price: 10,
  key: "tap-key-1234",
};

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("useSendGift (T-8.10)", () => {
  it("sends the price shown and the tap's key, and is marked as touching the wallet", async () => {
    const api = fakeApi({
      "POST /v1/gifts/send": () => json(200, { id: "s1" }),
    });
    const { client, Wrapper } = wrapper();
    const { result } = renderHook(() => useSendGift(), { wrapper: Wrapper });

    await act(() => result.current.mutateAsync(VARIABLES));

    expect(api.calls[0]?.body).toEqual({
      recipient_id: "u2",
      gift_id: "rose",
      shown_price: 10,
    });
    expect(api.calls[0]?.headers.get("Idempotency-Key")).toBe("tap-key-1234");
    expect(client.getMutationCache().getAll()[0]?.meta).toEqual({
      touchesWallet: true,
    });
  });

  it("asks the balance and every gift query again when it settles, refused too", async () => {
    fakeApi({
      "POST /v1/gifts/send": () =>
        envelope(429, "GIFT_COOLDOWN", { retry_after_s: 60 }),
    });
    const { client, Wrapper } = wrapper();
    for (const key of [
      queryKeys.wallet(),
      queryKeys.giftCatalogue(),
      queryKeys.giftCounts("u2"),
    ]) {
      client.setQueryData(key, {});
    }
    const { result } = renderHook(() => useSendGift(), { wrapper: Wrapper });

    act(() => result.current.mutate(VARIABLES));

    await waitFor(() => expect(result.current.isError).toBe(true));
    await waitFor(() => {
      for (const key of [
        queryKeys.wallet(),
        queryKeys.giftCatalogue(),
        queryKeys.giftCounts("u2"),
      ]) {
        expect(client.getQueryState(key)?.isInvalidated, String(key)).toBe(
          true,
        );
      }
    });
  });
});
