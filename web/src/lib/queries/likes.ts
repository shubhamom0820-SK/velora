import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type LikeCard = components["schemas"]["LikeCard"];

/**
 * Who liked or Super Liked me and is still waiting on my swipe (`GET /likes`,
 * T-6.7, D-542), newest first, a page at a time. A man sees an unrevealed one
 * as the server's blur only; a woman sees everyone.
 */
export function useLikes() {
  return useInfiniteQuery({
    queryKey: queryKeys.likes(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/likes", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/** How many `useLikes` lists (`GET /likes/count`): the header's badge. */
export function useLikesCount() {
  return useQuery({
    queryKey: queryKeys.likesCount(),
    queryFn: ({ signal }) => api.get("/v1/likes/count", { signal }),
  });
}

/**
 * Reveal one (`POST /likes/{handle}/reveal`): the `liked_you_reveal` row's
 * price for a man, charged once per pair, nothing for a woman. It sends the
 * price the screen showed (P-56, D-600), a woman's 0; a different price now
 * is `PRICE_CHANGED`, with nothing charged, and /prices is asked again. It spends
 * Velas, so the balance is asked again however it ends (`touchesWallet`);
 * the list is asked again so the tile shows who it was. A man who can't
 * afford it gets the store sheet (QueryProvider).
 */
export function useReveal() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { touchesWallet: true },
    mutationFn: ({
      handle,
      shownPrice,
    }: {
      handle: string;
      shownPrice: number;
    }) =>
      api.post("/v1/likes/{handle}/reveal", {
        params: { handle },
        body: { shown_price: shownPrice },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.likes() }),
  });
}
