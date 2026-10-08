import { useInfiniteQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type SearchResult = components["schemas"]["SearchResult"];

/**
 * `GET /search` (T-6.6, D-540): `@` and a username's start, across India, the
 * exact match first; or text, within the radius. A page at a time by the
 * API's cursor. `q` is what `searchQueryOf` made of the field, or null to ask
 * nothing.
 */
export function useSearch(q: string | null) {
  return useInfiniteQuery({
    queryKey: queryKeys.search(q ?? ""),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/search", {
        query: { q: q ?? "", cursor: pageParam },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled: q !== null,
  });
}
