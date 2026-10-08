import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type KudosKind = components["schemas"]["Kudos-Input"];

/**
 * Give someone kudos (`POST /kudos`, T-8.5): one of four kinds, once ever.
 * Their profile is asked again however it ends, so its `thread.kudos` says
 * `given` and the prompt goes (D-790).
 */
export function useGiveKudos() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ toId, kind }: { toId: string; kind: KudosKind }) =>
      api.post("/v1/kudos", { body: { to_id: toId, kind } }),
    onSettled: (_data, _error, { toId }) => {
      void client.invalidateQueries({ queryKey: queryKeys.profile(toId) });
    },
  });
}
