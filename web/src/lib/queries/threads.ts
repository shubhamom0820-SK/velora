import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Thread = components["schemas"]["Thread"];
/**
 * One Thread as its screen opens it (`GET /threads/{id}`, T-7.11, D-870): the
 * other person, and `send_price`, what my next text message costs now.
 */
export type ThreadView = components["schemas"]["ThreadView"];

/**
 * One of my Threads (`GET /threads/{id}`): `NOT_FOUND` for anyone else's and
 * across a block, which the screen shows as gone, never retried.
 */
export function useThread(id: string) {
  return useQuery({
    queryKey: queryKeys.thread(id),
    queryFn: ({ signal }) =>
      api.get("/v1/threads/{thread_id}", {
        params: { thread_id: id },
        signal,
      }),
    retry: false,
  });
}

/**
 * Asks again what a Thread's change moved: its screen (its status, its hour,
 * and what the next message costs) and every list it is in.
 */
function settleThread(client: QueryClient, id: string) {
  void client.invalidateQueries({ queryKey: queryKeys.thread(id) });
  void client.invalidateQueries({ queryKey: [...queryKeys.threads(), "list"] });
}

/**
 * What a re-open or an Extend sends (T-7.6). `shown_price` is the price the
 * button said, from `GET /prices` (P-56, D-600): the API refuses another with
 * `PRICE_CHANGED`. `key` is the tap's `Idempotency-Key`: made once per tap by
 * the screen (`crypto.randomUUID()`) and sent again with a retry of that tap,
 * so a retried tap is charged once (D-077).
 */
export type BuyTimeVariables = {
  thread_id: string;
  shown_price: number;
  key: string;
};

function buyTime(what: "reopen" | "extend") {
  return ({ thread_id, shown_price, key }: BuyTimeVariables) =>
    api.post(`/v1/threads/{thread_id}/${what}`, {
      params: { thread_id },
      body: { shown_price },
      headers: { "Idempotency-Key": key },
    });
}

/**
 * Re-opens an expired Thread for an hour from now (`POST
 * /threads/{id}/reopen`, T-7.6): his alone, priced `thread_reopen`. Spends
 * Velas, so the balance is asked again when it settles (T-5.5).
 */
export function useReopenThread() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: buyTime("reopen"),
    meta: { touchesWallet: true },
    onSettled: (_data, _error, { thread_id }) =>
      settleThread(client, thread_id),
  });
}

/**
 * Extends a Thread by `thread_extend_hours` on top of what is left, or from
 * now once expired (`POST /threads/{id}/extend`, T-7.6, D-253): his alone,
 * priced `thread_extend`.
 */
export function useExtendThread() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: buyTime("extend"),
    meta: { touchesWallet: true },
    onSettled: (_data, _error, { thread_id }) =>
      settleThread(client, thread_id),
  });
}

/**
 * Taps "Tie the knot" (`POST /threads/{id}/knot`, T-7.7, D-770): free (D-003),
 * on a live or an expired Thread. Answers the Thread: `knotted` when this tap
 * was the second, which the screen celebrates (P-670); otherwise `i_tied`, and
 * the other person is asked. A tap already there returns it as it is.
 */
export function useTieKnot() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post("/v1/threads/{thread_id}/knot", { params: { thread_id: id } }),
    onSettled: (_data, _error, id) => settleThread(client, id),
  });
}

/**
 * Unties a Knot (`DELETE /threads/{id}/knot`, D-770): either of the two may.
 * A Thread from a match gets a fresh hour; a private message never expires.
 */
export function useUntieKnot() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete("/v1/threads/{thread_id}/knot", { params: { thread_id: id } }),
    onSettled: (_data, _error, id) => settleThread(client, id),
  });
}

export type ThreadRow = components["schemas"]["ThreadRow"];
type ThreadRowPage = components["schemas"]["ThreadRowPage"];
export type Tier = "threads" | "knots";
export type ThreadFilter = "all" | "unread" | "recent";

/**
 * A page of the chats list: the API's largest (1 to 50, `core/pagination`), so
 * a tab's count reads one page, and "50+" beyond it (T-7.10).
 */
export const THREADS_PAGE = 50;

/** A search is 1 to 50 characters (`GET /threads?q=`); anything else the API refuses. */
export const THREADS_Q_MAX = 50;

/** One request clears 1 to 100 chosen chats (`POST /threads/clear`). */
export const CLEAR_MAX = 100;

/**
 * The chats list (`GET /threads`, T-7.2): one tier, newest first, a page at a
 * time. `q` is sent only when it says something, as the API takes it (1 to 50
 * characters); never a cleared Thread with nothing newer, never across a block.
 */
export function useThreads(
  tier: Tier,
  filter: ThreadFilter,
  q: string,
  enabled = true,
) {
  return useInfiniteQuery({
    queryKey: queryKeys.threadList(tier, filter, q),
    enabled,
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/threads", {
        query: {
          tier,
          filter,
          q: q === "" ? undefined : q,
          cursor: pageParam,
          limit: THREADS_PAGE,
        },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

type Snapshot = [QueryKey, InfiniteData<ThreadRowPage> | undefined][];

/** Takes `id` out of every list now, and returns what was there to put back. */
async function takeOut(client: QueryClient, id: string): Promise<Snapshot> {
  const lists = [...queryKeys.threads(), "list"];
  await client.cancelQueries({ queryKey: lists });
  const before = client.getQueriesData<InfiniteData<ThreadRowPage>>({
    queryKey: lists,
  });
  client.setQueriesData<InfiniteData<ThreadRowPage>>(
    { queryKey: lists },
    (data) =>
      data && {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.filter((row) => row.id !== id),
        })),
      },
  );
  return before;
}

/**
 * Clears one Thread from my chats (`POST /threads/{id}/clear`, T-7.8): mine
 * alone, through its newest message; the other person sees no change. The row
 * leaves the list at once and comes back if the API refuses.
 */
export function useClearThread() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post("/v1/threads/{thread_id}/clear", {
        params: { thread_id: id },
      }),
    onMutate: (id) => takeOut(client, id),
    onError: (_error, _id, before) => {
      for (const [key, data] of before ?? []) client.setQueryData(key, data);
    },
    // Not awaited: the screen's toast never waits on the list's refetch.
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.threads() });
    },
  });
}

/**
 * Undo (`DELETE /threads/{id}/clear`, D-611): the clearing gone and the
 * history back. It removes the clearing altogether, so an earlier one goes with
 * it: P-620.
 */
export function useRestoreThread() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete("/v1/threads/{thread_id}/clear", {
        params: { thread_id: id },
      }),
    // Not awaited: the screen's toast never waits on the list's refetch.
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.threads() });
    },
  });
}

/**
 * Clears several (`POST /threads/clear`): the chats chosen in select mode, or
 * `expired`, every Thread in my list expired by the clock, as the server
 * counts them (D-560). Answers how many it cleared.
 */
export function useClearThreads() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (what: { thread_ids: string[] } | { expired: true }) =>
      api.post("/v1/threads/clear", { body: what }),
    // Not awaited: the screen's toast never waits on the list's refetch.
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.threads() });
    },
  });
}
