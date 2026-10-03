import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useSession } from "@/store/session";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Me = components["schemas"]["Me"];

/** The signed-in person (`GET /me`, T-3.5). Asked for only once there's a session. */
export function useMe() {
  const signedIn = useSession((state) => state.status === "signed-in");
  return useQuery({
    queryKey: queryKeys.me(),
    queryFn: ({ signal }) => api.get("/v1/me", { signal }),
    enabled: signedIn,
  });
}
