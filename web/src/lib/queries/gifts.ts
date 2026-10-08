import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Gift = components["schemas"]["Gift"];
export type GiftCatalogue = components["schemas"]["GiftCatalogue"];
export type ReceivedGift = components["schemas"]["ReceivedGift"];

/**
 * The gifts on sale, by `sort` (`GET /gifts`, T-8.9), and for a man his free
 * sends left this week and when they come back (D-652); both null for anyone
 * else. Each gift's price is its row's, never `/prices` (gifts aren't in it).
 */
export function useGifts({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.giftCatalogue(),
    queryFn: ({ signal }) => api.get("/v1/gifts", { signal }),
    enabled,
  });
}

/**
 * What one gift's send carries (T-8.10). `shown_price` is the price the sheet
 * showed: 0 while a free send is left this week, else the gift's `credits`
 * from `GET /gifts` (P-56, D-600, D-650); the API refuses another with
 * `PRICE_CHANGED`. `key` is the tap's `Idempotency-Key`, sent again with a
 * retry of that tap, so a retried send is one send (D-653).
 */
export type SendGiftVariables = {
  recipient_id: string;
  gift_id: string;
  shown_price: number;
  key: string;
};

/**
 * Sends a gift (`POST /gifts/send`, T-8.9): his alone. It may spend Velas, so
 * the balance is asked again when it settles (T-5.5), and so are his free
 * sends and her counts, whatever the answer: a send that timed out may still
 * have landed.
 */
export function useSendGift() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      recipient_id,
      gift_id,
      shown_price,
      key,
    }: SendGiftVariables) =>
      api.post("/v1/gifts/send", {
        body: { recipient_id, gift_id, shown_price },
        headers: { "Idempotency-Key": key },
      }),
    meta: { touchesWallet: true },
    // Not awaited: the sheet's toast never waits on the refetch.
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.gifts() });
    },
  });
}

/**
 * How many of each gift someone received, in the catalogue's order, never
 * from whom (`GET /users/{id}/gifts`, T-8.9). Empty when she turned
 * `show_gifts` off, to everyone but herself.
 */
export function useGiftCounts(userId: string) {
  return useQuery({
    queryKey: queryKeys.giftCounts(userId),
    queryFn: ({ signal }) =>
      api.get("/v1/users/{user_id}/gifts", {
        params: { user_id: userId },
        signal,
      }),
  });
}

/**
 * The gifts she received, newest first, a page at a time (`GET /me/gifts`,
 * T-8.9): who sent each, never what he paid or whether it was free (D-652).
 */
export function useReceivedGifts({
  enabled = true,
}: { enabled?: boolean } = {}) {
  return useInfiniteQuery({
    queryKey: queryKeys.receivedGifts(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/me/gifts", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled,
  });
}
