import {
  useMutation,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type ReportReason = components["schemas"]["ReportReason"];
export type FileReport = components["schemas"]["FileReportRequest"];

/** `reports.details` is 500 characters at most (03-SCHEMA §5). */
export const REPORT_DETAILS_MAX = 500;

/**
 * After a block, every list and profile the other person could be in is
 * stale: the feeds, search, Liked you, the chats and their profile (T-9.1).
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
