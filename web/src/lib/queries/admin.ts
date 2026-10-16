import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

type Schemas = components["schemas"];
export type AdminUser = Schemas["AdminUser"];
export type AdminUserDetail = Schemas["AdminUserDetail"];
export type AdminReport = Schemas["AdminReport"];
export type AdminPhoto = Schemas["AdminPhoto"];
export type AdminMessage = Schemas["AdminMessage"];
export type AuditEntry = Schemas["AuditEntry"];
export type AdminFreeze = Schemas["AdminFreeze"];
export type AdminClaim = Schemas["AdminRefundRequest"];
export type AdminMetrics = Schemas["AdminMetrics"];
export type ReportAction = Schemas["ReportAction"];
export type StatusTarget = Schemas["StatusTarget"];
export type ClaimAction = Schemas["ClaimAction"];
export type StaffRejectReason = "nudity" | "text_overlay" | "other";

/**
 * The admin panel's server data (T-9.5). Every read writes `audit_log` on the
 * API (D-920), so nothing here asks again by itself: not on focus, not on
 * reconnect, not when a screen mounts again within the minute. Staff ask again
 * with each screen's own button, and an action asks every admin list again.
 */
const ONCE = {
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  staleTime: 60_000,
} as const;

export function useAdminMetrics() {
  return useQuery({
    ...ONCE,
    queryKey: queryKeys.adminMetrics(),
    queryFn: ({ signal }) => api.get("/v1/admin/metrics", { signal }),
  });
}

export function useAdminUsers(q: string) {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminUsers(q),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/users", {
        query: { q: q || undefined, cursor: pageParam },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useAdminUser(id: string) {
  return useQuery({
    ...ONCE,
    queryKey: queryKeys.adminUser(id),
    queryFn: ({ signal }) =>
      api.get("/v1/admin/users/{user_id}", { params: { user_id: id }, signal }),
  });
}

export function useAdminReports(status: Schemas["ReportStatus"] = "open") {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminReports(status),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/reports", {
        query: { status, cursor: pageParam },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useAdminModeration() {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminModeration(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/moderation", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/**
 * A Thread's messages, every one (D-924): asked only once staff have said why,
 * and each page's read is audited with that reason.
 */
export function useAdminThread(id: string, reason: string | null) {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminThread(id, reason ?? ""),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/threads/{thread_id}/messages", {
        params: { thread_id: id },
        query: { reason: reason ?? "", cursor: pageParam },
        signal,
      }),
    enabled: reason !== null,
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useAdminAudit(action: string) {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminAudit(action),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/audit", {
        query: { action: action || undefined, cursor: pageParam },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useAdminFreezes() {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminFreezes(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/freezes", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/** The open claims (T-8.3, D-582), oldest first: an admin's alone (P-480). */
export function useAdminClaims() {
  return useInfiniteQuery({
    ...ONCE,
    queryKey: queryKeys.adminClaims(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/admin/refund-requests", {
        query: { status: "open", cursor: pageParam },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/** After any action, every admin list and figure is asked again. */
function useAskAgain() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: queryKeys.admin() });
}

export function useSetStatus(userId: string) {
  const askAgain = useAskAgain();
  return useMutation({
    mutationFn: (body: { status: StatusTarget; reason: string }) =>
      api.post("/v1/admin/users/{user_id}/status", {
        params: { user_id: userId },
        body,
      }),
    onSuccess: askAgain,
  });
}

/**
 * An admin's grant or correction (D-923), under the key the form made when it
 * opened, so a retry is the same change and the API applies it once.
 */
export function useChangeCredits(userId: string) {
  const askAgain = useAskAgain();
  return useMutation({
    mutationFn: ({
      delta,
      reason,
      key,
    }: {
      delta: number;
      reason: string;
      key: string;
    }) =>
      api.post("/v1/admin/users/{user_id}/credits", {
        params: { user_id: userId },
        body: { delta, reason },
        headers: { "Idempotency-Key": key },
      }),
    onSuccess: askAgain,
  });
}

export function useResolveReport() {
  const askAgain = useAskAgain();
  return useMutation({
    mutationFn: ({
      id,
      action,
      note,
    }: {
      id: string;
      action: ReportAction;
      note: string;
    }) =>
      api.post("/v1/admin/reports/{report_id}/resolve", {
        params: { report_id: id },
        body: { action, note },
      }),
    onSuccess: askAgain,
  });
}

export function useDecidePhoto() {
  const askAgain = useAskAgain();
  return useMutation({
    mutationFn: ({
      id,
      approve,
      reason,
      note,
    }: {
      id: string;
      approve: boolean;
      reason?: StaffRejectReason;
      note?: string;
    }) =>
      api.post("/v1/admin/photos/{photo_id}/decide", {
        params: { photo_id: id },
        body: approve ? { approve } : { approve, reason, note },
      }),
    onSuccess: askAgain,
  });
}

export function useResolveClaim() {
  const askAgain = useAskAgain();
  return useMutation({
    mutationFn: ({
      id,
      action,
      note,
    }: {
      id: string;
      action: ClaimAction;
      note: string;
    }) =>
      api.post("/v1/admin/refund-requests/{claim_id}/resolve", {
        params: { claim_id: id },
        body: { action, note },
      }),
    onSuccess: askAgain,
  });
}
