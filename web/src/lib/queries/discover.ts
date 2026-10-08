import { useInfiniteQuery, useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Card = components["schemas"]["Card"];
export type Feed = components["schemas"]["Feed"];
export type SwipeDirection = components["schemas"]["SwipeDirection"];
export type SwipeResult = components["schemas"]["SwipeResult"];

/** The filters the feed takes (T-6.9's sheet sets them; T-6.5 reads them). */
export type DiscoverFilters = {
  intentIds: readonly number[];
  verified: boolean;
};

/** How many cards a page asks for: the deck asks for the next at 5 left. */
export const DISCOVER_PAGE_SIZE = 20;

/**
 * The deck (`GET /discover`, T-6.2), a page at a time by the API's cursor,
 * which carries the instant the scroll began (D-491). Never asked again on
 * focus or on a timer: a refetch would rank the scroll afresh under the
 * person mid-swipe, and everyone already swiped is gone from it anyway.
 * Each page also says a man's swipes left today (`swipes_left`, T-6.5).
 */
export function useDiscover(feed: Feed, filters: DiscoverFilters) {
  return useInfiniteQuery({
    queryKey: queryKeys.discover(feed, filters),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/discover", {
        query: {
          feed,
          intent_ids: [...filters.intentIds],
          verified: filters.verified || undefined,
          cursor: pageParam,
          limit: DISCOVER_PAGE_SIZE,
        },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
  });
}

export type SwipeVariables = {
  target_id: string;
  dir: SwipeDirection;
  /** The price the screen showed: a man's Super Like's, else 0 (P-56, D-600). */
  shown_price: number;
};

/**
 * A swipe (`POST /swipes`, T-6.4). A Super Like spends Velas, so it is marked
 * `touchesWallet` and the balance is asked again when it settles (T-5.5); a
 * like or a pass isn't. Never retried: a retried Super Like would be refused
 * as `ALREADY_EXISTS`, but a retry is still a second request nobody asked for.
 */
export function useSwipe() {
  return useMutation({
    mutationFn: (variables: SwipeVariables) =>
      api.post("/v1/swipes", { body: variables }),
  });
}

/** `useSwipe` for a Super Like: the same request, marked as spending. */
export function useSuperLike() {
  return useMutation({
    mutationFn: (variables: SwipeVariables) =>
      api.post("/v1/swipes", { body: variables }),
    meta: { touchesWallet: true },
  });
}

/**
 * Opens the match's Thread (`POST /threads`, T-7.1): 5 Velas for him, free for
 * her. `shown_price` is what the button said (P-56, D-600).
 */
export function useOpenThread() {
  return useMutation({
    mutationFn: (variables: { match_id: string; shown_price: number }) =>
      api.post("/v1/threads", { body: variables }),
    meta: { touchesWallet: true },
  });
}
