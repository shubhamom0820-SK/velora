import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Album = components["schemas"]["Album"];
export type AlbumRequest = components["schemas"]["AlbumRequest"];

/** A page of the requests to see your album: 20, the API's default. */
export const ALBUM_REQUESTS_PAGE = 20;

/**
 * Someone's private album as the viewer may see it (`GET /users/{id}/album`,
 * D-732): `status`, the viewer's latest request to them (null if they never
 * asked), and the viewer's own watermarked copies, signed for 10 minutes,
 * only while it is granted. While a grant's copies are still being made, it
 * asks again every few seconds until they are there.
 */
export function useAlbum(id: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.album(id),
    queryFn: ({ signal }) =>
      api.get("/v1/users/{user_id}/album", {
        params: { user_id: id },
        signal,
      }),
    enabled,
    refetchInterval: (query) =>
      query.state.data?.status === "granted" &&
      query.state.data.photos.length === 0
        ? COPIES_POLL_MS
        : false,
  });
}

const COPIES_POLL_MS = 5_000;

/**
 * Ask to see someone's album (`POST /album-requests`, T-8.4): the
 * `album_request` price for a man, nothing for a woman. It sends the price the
 * screen showed (P-56, D-600), a woman's 0, and a different price now is
 * `PRICE_CHANGED`, nothing charged. It spends Velas, so the balance is asked
 * again however it ends (`touchesWallet`); the album is asked again so it says
 * the request is waiting.
 */
export function useRequestAlbum() {
  const client = useQueryClient();
  return useMutation({
    meta: { touchesWallet: true },
    mutationFn: ({
      ownerId,
      shownPrice,
    }: {
      ownerId: string;
      shownPrice: number;
    }) =>
      api.post("/v1/album-requests", {
        body: { owner_id: ownerId, shown_price: shownPrice },
      }),
    onSettled: (_data, _error, { ownerId }) => {
      void client.invalidateQueries({ queryKey: queryKeys.album(ownerId) });
    },
  });
}

/**
 * The requests to see your album (`GET /album-requests/incoming`, D-732):
 * pending and granted, newest first, none from across a block.
 */
export function useIncomingAlbumRequests() {
  return useInfiniteQuery({
    queryKey: queryKeys.albumIncoming(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/album-requests/incoming", {
        query: { cursor: pageParam, limit: ALBUM_REQUESTS_PAGE },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/**
 * Grant or decline one (`POST /album-requests/{id}/decide`). A grant has
 * their copies made (`watermark_album`); a decline returns nothing (D-230).
 * The list is asked again however it ends.
 */
export function useDecideAlbumRequest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, grant }: { id: string; grant: boolean }) =>
      api.post("/v1/album-requests/{request_id}/decide", {
        params: { request_id: id },
        body: { grant },
      }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.albumIncoming() });
    },
  });
}

/**
 * Stop sharing a granted album (`POST /album-requests/{id}/revoke`): their
 * copies are deleted (D-730).
 */
export function useRevokeAlbumRequest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post("/v1/album-requests/{request_id}/revoke", {
        params: { request_id: id },
      }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.albumIncoming() });
    },
  });
}
