import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

export type Thread = components["schemas"]["Thread"];

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
  return useMutation({
    mutationFn: buyTime("reopen"),
    meta: { touchesWallet: true },
  });
}

/**
 * Extends a Thread by `thread_extend_hours` on top of what is left, or from
 * now once expired (`POST /threads/{id}/extend`, T-7.6, D-253): his alone,
 * priced `thread_extend`.
 */
export function useExtendThread() {
  return useMutation({
    mutationFn: buyTime("extend"),
    meta: { touchesWallet: true },
  });
}
