import type { DiscoverFilters } from "@/lib/queries/discover";

/**
 * The deck's filters live in the URL (T-6.5, T-6.9), and this file is the one
 * place that reads them from it and writes them to it: the filter sheet's
 * "Show people" and the empty deck's "Clear filters" both go through
 * `hrefOf`. The server applies them (T-6.2's query, D-660); the browser only
 * carries them.
 */

/** No filter: everyone the feed would show. */
export const NO_FILTERS: DiscoverFilters = {
  intentIds: [],
  verified: false,
  online: false,
};

/** The filters in the URL's search params. */
export function filtersOf(params: URLSearchParams): DiscoverFilters {
  const intentIds = params
    .getAll("intent_ids")
    .map(Number)
    .filter((id) => Number.isInteger(id) && id > 0);
  return {
    intentIds: [...new Set(intentIds)],
    verified: params.get("verified") === "true",
    online: params.get("online") === "true",
  };
}

/** `pathname` with `filters` as its search params, and nothing else. */
export function hrefOf(pathname: string, filters: DiscoverFilters): string {
  const params = new URLSearchParams();
  for (const id of filters.intentIds) params.append("intent_ids", String(id));
  if (filters.verified) params.set("verified", "true");
  if (filters.online) params.set("online", "true");
  const search = params.toString();
  return search ? `${pathname}?${search}` : pathname;
}

/** The badge's number, as the prototype counts it: each intent, each toggle. */
export function activeCount(filters: DiscoverFilters): number {
  return (
    filters.intentIds.length +
    (filters.verified ? 1 : 0) +
    (filters.online ? 1 : 0)
  );
}
