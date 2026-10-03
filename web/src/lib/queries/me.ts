import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useSession } from "@/store/session";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Me = components["schemas"]["Me"];

/**
 * How long `Me` counts as fresh. Every write that changes it answers with the
 * new one, which goes straight into the cache, so a screen opening right after
 * needn't ask again: each `/me` is a round trip of 1.8 to 3 s on staging today
 * (P-49), and T-3.11's Chrome check saw one per onboarding step. A named
 * constant, a Checklist A exception like T-3.10's: the browser's cache, not a
 * limit the server enforces.
 */
export const ME_FRESH_FOR_MS = 60_000;

/** The signed-in person (`GET /me`, T-3.5). Asked for only once there's a session. */
export function useMe() {
  const signedIn = useSession((state) => state.status === "signed-in");
  return useQuery({
    queryKey: queryKeys.me(),
    queryFn: ({ signal }) => api.get("/v1/me", { signal }),
    enabled: signedIn,
    staleTime: ME_FRESH_FOR_MS,
  });
}
