import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type LedgerEntry = components["schemas"]["LedgerEntry"];
export type LedgerReason = components["schemas"]["LedgerReason"];

/**
 * A man's balance (`GET /wallet`, T-5.3). The header's pill and the wallet's
 * card read this one query, never `Me.balance`, which is cached for a minute
 * and can disagree with it (P-221).
 *
 * Asked again whenever the window regains focus, however fresh, and when a
 * mutation marked `touchesWallet` settles (QueryProvider). Never on a timer:
 * live updates arrive with the socket (T-7.12). Both are set here rather than
 * left to TanStack's defaults, so a later default can't change them.
 */
export function useWallet({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.wallet(),
    queryFn: ({ signal }) => api.get("/v1/wallet", { signal }),
    enabled,
    refetchOnWindowFocus: "always",
    refetchInterval: false,
  });
}

/**
 * A man's history (`GET /wallet/ledger`, T-5.3), newest first, a page at a
 * time by the API's cursor; `next_cursor` is null on the last page.
 */
export function useLedger() {
  return useInfiniteQuery({
    queryKey: queryKeys.walletLedger(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/wallet/ledger", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/**
 * What each active action costs a man, in Velas (`GET /prices`, T-5.2), keyed
 * by the debit reason it is charged under. A switched-off action isn't in it.
 */
export function usePrices() {
  return useQuery({
    queryKey: queryKeys.prices(),
    queryFn: ({ signal }) => api.get("/v1/prices", { signal }),
  });
}
