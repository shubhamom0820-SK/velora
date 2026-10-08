import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, json } from "@/lib/testing/fakeApi";

import { queryKeys } from "./keys";
import { useBlock, useReport } from "./safety";

const STALE_AFTER_A_BLOCK = [
  queryKeys.discover("for_you", {
    intentIds: [],
    verified: false,
    online: false,
  }),
  queryKeys.search("@simran"),
  queryKeys.likes(),
  queryKeys.threadList("threads", "all", ""),
  queryKeys.profile("u2"),
  queryKeys.profileByUsername("simran.k"),
];

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  for (const key of STALE_AFTER_A_BLOCK) client.setQueryData(key, {});
  client.setQueryData(queryKeys.wallet(), { balance: 5 });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const stale = (key: readonly unknown[]) =>
    client.getQueryState(key)?.isInvalidated;
  return { client, wrapper, stale };
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("reports and blocks (T-9.1)", () => {
  it("a block marks every list and profile stale, and asks none of them again", async () => {
    const api = fakeApi({ "POST /v1/blocks": () => json(201, {}) });
    const { wrapper, stale } = setup();
    const { result } = renderHook(() => useBlock(), { wrapper });

    await act(() => result.current.mutateAsync("u2"));

    for (const key of STALE_AFTER_A_BLOCK) expect(stale(key)).toBe(true);
    expect(stale(queryKeys.wallet())).toBe(false);
    expect(api.sent()).toEqual(["POST /v1/blocks"]);
  });

  it("a report with also-block does the same, and one without touches nothing", async () => {
    const api = fakeApi({
      "POST /v1/reports": () => json(201, { id: "r1", created_at: "x" }),
    });
    const { wrapper, stale } = setup();
    const { result } = renderHook(() => useReport(), { wrapper });

    await act(() =>
      result.current.mutateAsync({
        reported_id: "u2",
        reason: "fake",
        also_block: false,
      }),
    );
    for (const key of STALE_AFTER_A_BLOCK) expect(stale(key)).toBe(false);

    await act(() =>
      result.current.mutateAsync({
        reported_id: "u2",
        reason: "harass",
        also_block: true,
      }),
    );
    for (const key of STALE_AFTER_A_BLOCK) expect(stale(key)).toBe(true);
    expect(api.sent()).toEqual(["POST /v1/reports", "POST /v1/reports"]);
  });
});
