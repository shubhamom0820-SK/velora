import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

import { queryKeys } from "./keys";

/** The API's liveness probe. Only `/dev/health` uses it, to prove the data layer end to end. */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) => api.get("/healthz", { signal }),
  });
}
