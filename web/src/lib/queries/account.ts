import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/session";
import { useSession } from "@/store/session";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type DataExport = components["schemas"]["DataExport"];

/**
 * How often a copy being made is asked about again: the worker makes one in
 * seconds (D-502). A named constant, a Checklist A exception like
 * `VERIFICATION_POLL_MS`: the browser's pace, not a limit the server enforces.
 */
export const EXPORT_POLL_MS = 3_000;

/**
 * Pause (`POST /me/pause`, T-9.6) or resume (`DELETE /me/pause`): hidden from
 * everyone and sent nothing while paused. Both answer 204, so `Me` is asked
 * again for its `status`.
 */
export function usePause() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (paused: boolean) =>
      paused ? api.post("/v1/me/pause") : api.delete("/v1/me/pause"),
    onSettled: () => client.invalidateQueries({ queryKey: queryKeys.me() }),
  });
}

/**
 * The newest copy of your data (`GET /me/export`, D-502), or `null` when none
 * was ever asked for (`NOT_FOUND`). Asked again every few seconds while it is
 * being made.
 */
export function useDataExport() {
  return useQuery({
    queryKey: queryKeys.dataExport(),
    queryFn: async ({ signal }): Promise<DataExport | null> => {
      try {
        return await api.get("/v1/me/export", { signal });
      } catch (error) {
        if (error instanceof ApiError && error.code === "NOT_FOUND")
          return null;
        throw error;
      }
    },
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ? EXPORT_POLL_MS : false,
  });
}

/**
 * Ask for a copy (`POST /me/export`): a new one, or the one being made, or a
 * ready one, never a second (D-502). Five a day.
 */
export function useRequestExport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/v1/me/export"),
    onSuccess: (made) => client.setQueryData(queryKeys.dataExport(), made),
  });
}

/**
 * Delete the account (`DELETE /me`, D-500): `deleted` at once, every session
 * revoked. Then this tab signs out as sign-out does, and nobody's data stays
 * in the cache. The API has already revoked the session, so a sign-out the
 * API refuses is still a sign-out here.
 */
export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete("/v1/me"),
    onSuccess: async () => {
      try {
        await logout();
      } catch {
        useSession.getState().signOut();
      }
      client.clear();
    },
  });
}
