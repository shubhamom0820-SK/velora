import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type ReportReason = components["schemas"]["ReportReason"];
export type FileReport = components["schemas"]["FileReportRequest"];
export type BlockedUser = components["schemas"]["BlockedUser"];
export type FiledReport = components["schemas"]["FiledReport"];

/** `reports.details` is 500 characters at most (03-SCHEMA §5). */
export const REPORT_DETAILS_MAX = 500;

/**
 * After a block, every list and profile the other person could be in is
 * stale: the feeds, search, Liked you, the chats and their profile (T-9.1),
 * and the blocked list (T-9.8); after an unblock, the same.
 * Marked, never asked again here: the screen the block was made on stays as
 * it is until the person leaves it, and each is asked afresh when next shown.
 */
function afterBlock(queryClient: QueryClient) {
  for (const queryKey of [
    queryKeys.feeds(),
    queryKeys.searches(),
    queryKeys.likes(),
    queryKeys.threads(),
    queryKeys.profiles(),
    queryKeys.blocks(),
  ]) {
    void queryClient.invalidateQueries({ queryKey, refetchType: "none" });
  }
}

/**
 * Report someone (`POST /reports`, T-9.1): to moderation, never told to them.
 * With `also_block`, the block is made in the same request.
 */
export function useReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FileReport) => api.post("/v1/reports", { body }),
    onSuccess: (_filed, body) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.filedReports(),
        refetchType: "none",
      });
      if (body.also_block) afterBlock(queryClient);
    },
  });
}

/**
 * Block someone (`POST /blocks`, T-9.1): neither sees the other anywhere,
 * and they're never told (D-862).
 */
export function useBlock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      api.post("/v1/blocks", { body: { user_id: userId } }),
    onSuccess: () => afterBlock(queryClient),
  });
}

/**
 * Whom you block now (`GET /blocks`, T-9.1), newest first, a page at a time:
 * the You tab's list (T-9.8). Never who blocks you.
 */
export function useBlockedUsers() {
  return useInfiniteQuery({
    queryKey: queryKeys.blocks(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/blocks", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/**
 * Lift a block (`DELETE /blocks/{user_id}`, D-860): kept on record, blocking
 * nothing. Every list and profile they could be in is stale again, as after a
 * block, and the blocked list is asked again.
 */
export function useUnblock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      api.delete("/v1/blocks/{user_id}", { params: { user_id: userId } }),
    onSuccess: () => {
      afterBlock(queryClient);
      void queryClient.invalidateQueries({ queryKey: queryKeys.blocks() });
    },
  });
}

/**
 * The reports you filed (`GET /reports`, T-9.8, D-911), newest first: never a
 * status, never one about you.
 */
export function useFiledReports() {
  return useInfiniteQuery({
    queryKey: queryKeys.filedReports(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/reports", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}
