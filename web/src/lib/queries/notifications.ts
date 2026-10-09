import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import * as push from "@/lib/push";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Notification = components["schemas"]["Notification"];
export type Prefs = components["schemas"]["Prefs"];
export type PrefsPatch = components["schemas"]["PrefsPatch"];

/**
 * The VAPID public key (`GET /push/key`, T-9.4), or null where this build
 * has no push (local and CI: the API answers 404, D-856), and then nothing
 * offers it. Asked once a session.
 */
export function usePushKey({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.pushKey(),
    queryFn: async ({ signal }) => {
      try {
        return (await api.get("/v1/push/key", { signal })).public_key;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/** This browser's subscription, or null: whether its switch is on. */
export function usePushSubscription() {
  return useQuery({
    queryKey: [...queryKeys.pushKey(), "this-browser"] as const,
    queryFn: () => push.current(),
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * Turn push on in this browser: ask, subscribe, and send the subscription.
 * Null when the person said no to the browser's ask.
 */
export function useTurnOnPush() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (publicKey: string) => {
      const body = await push.subscribe(publicKey);
      if (body) await api.post("/v1/push/subscriptions", { body });
      return body;
    },
    onSettled: () =>
      client.invalidateQueries({ queryKey: queryKeys.pushKey() }),
  });
}

/** Turn push off in this browser, and tell the API to forget it. */
export function useTurnOffPush() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const endpoint = await push.unsubscribe();
      if (endpoint) {
        await api.delete("/v1/push/subscriptions", { body: { endpoint } });
      }
    },
    onSettled: () =>
      client.invalidateQueries({ queryKey: queryKeys.pushKey() }),
  });
}

/** Which kinds may push, and "Hide names" (`GET /notification-prefs`). */
export function useNotificationPrefs() {
  return useQuery({
    queryKey: queryKeys.notificationPrefs(),
    queryFn: ({ signal }) => api.get("/v1/notification-prefs", { signal }),
  });
}

/** One setting changed; the answer is every setting as saved. */
export function useUpdateNotificationPrefs() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: PrefsPatch) =>
      api.patch("/v1/notification-prefs", { body: patch }),
    onSuccess: (prefs) =>
      client.setQueryData(queryKeys.notificationPrefs(), prefs),
  });
}

/** The in-app list (`GET /notifications`), newest first, a page at a time. */
export function useNotifications() {
  return useInfiniteQuery({
    queryKey: queryKeys.notifications(),
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/notifications", { query: { cursor: pageParam }, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/** Every unread notification read (`POST /notifications/read`). */
export function useMarkNotificationsRead() {
  return useMutation({
    mutationFn: () => api.post("/v1/notifications/read"),
  });
}
