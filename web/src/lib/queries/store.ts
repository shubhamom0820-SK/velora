import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Pack = components["schemas"]["Pack"];
export type Order = components["schemas"]["Order"];
export type ClaimReason = components["schemas"]["ClaimReason"];

/** How often the store asks whether the webhook has landed (T-8.7's line). */
export const POLL_EVERY_MS = 1_500;
/** How long it asks before saying it is still waiting (T-8.7's line). */
export const POLL_FOR_MS = 60_000;

/**
 * A man's store (`GET /packs`, T-8.1): his packs in order, each with the
 * first-purchase bonus he would get buying it now, or 0. A woman is refused
 * (`NOT_ALLOWED`), so the store asks only for a man (`enabled`).
 */
export function usePacks({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.packs(),
    queryFn: ({ signal }) => api.get("/v1/packs", { signal }),
    enabled,
  });
}

/**
 * An order for a pack (`POST /payments/orders`, T-8.1): the pack's id only,
 * since the amount and the Velas come from its row (rule 6), so it carries no
 * `shown_price`; the store compares the order's `amount_paise` with the price
 * it showed instead (D-761). `key` is the Idempotency-Key: the same key is the
 * same order, which is how "Try again" reopens it rather than making a second
 * (D-761). Marked `touchesWallet` as every mutation near money is, though the
 * Velas arrive by the webhook and the poll below refreshes the balance itself.
 */
export function useCreateOrder() {
  return useMutation({
    meta: { touchesWallet: true },
    mutationFn: ({ packId, key }: { packId: string; key: string }) =>
      api.post("/v1/payments/orders", {
        body: { pack_id: packId },
        headers: { "Idempotency-Key": key },
      }),
  });
}

export type PaymentWait =
  | { state: "waiting" }
  | { state: "paid"; velas: number }
  | { state: "timedOut" };

/**
 * After Checkout says the payment went through: `GET /payments/{id}` every
 * 1.5 s until it reads `paid`, for 60 s at most (T-8.7). Only `paid` ends it.
 * `failed` doesn't: one order can fail and then be captured (T-8.2), and
 * Razorpay lets a man try another method inside its window, so a failed first
 * attempt reads `failed` while the second is on its way. Paid, the balance,
 * the history and the packs (whose bonus is gone after a first purchase) are
 * asked again. `attempt` restarts the 60 s ("Check again").
 */
export function usePaymentWait(
  paymentId: string | null,
  attempt = 0,
): PaymentWait {
  const queryClient = useQueryClient();
  const [timedOut, setTimedOut] = useState<string | null>(null);
  const key = paymentId === null ? null : `${paymentId}:${attempt}`;
  const expired = key !== null && timedOut === key;

  useEffect(() => {
    if (key === null) return;
    const timer = setTimeout(() => setTimedOut(key), POLL_FOR_MS);
    return () => clearTimeout(timer);
  }, [key]);

  const status = useQuery({
    queryKey: queryKeys.payment(paymentId ?? ""),
    queryFn: ({ signal }) =>
      api.get("/v1/payments/{payment_id}", {
        params: { payment_id: paymentId ?? "" },
        signal,
      }),
    enabled: paymentId !== null && !expired,
    refetchInterval: (query) =>
      query.state.data?.status === "paid" ? false : POLL_EVERY_MS,
    refetchIntervalInBackground: true,
    staleTime: 0,
    gcTime: 0,
  });

  const paid = status.data?.status === "paid";
  useEffect(() => {
    if (!paid) return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.wallet() });
    void queryClient.invalidateQueries({ queryKey: queryKeys.packs() });
  }, [paid, queryClient]);

  if (paid && status.data) {
    return {
      state: "paid",
      velas: status.data.credits + status.data.bonus_credits,
    };
  }
  return expired ? { state: "timedOut" } : { state: "waiting" };
}

/**
 * A broken payment's claim (`POST /refund-requests`, T-8.3, D-580): his own
 * payment and one of the two kinds, nothing in his words. Refused because the
 * Velas were granted after all (`NOT_ALLOWED`, `velas_granted`): the balance
 * is asked again, so it shows them.
 */
export function useClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    onError: (error) => {
      if (error instanceof ApiError && error.code === "NOT_ALLOWED") {
        void queryClient.invalidateQueries({ queryKey: queryKeys.wallet() });
      }
    },
    mutationFn: ({
      paymentId,
      reason,
    }: {
      paymentId: string;
      reason: ClaimReason;
    }) =>
      api.post("/v1/refund-requests", {
        body: { payment_id: paymentId, reason },
      }),
  });
}

/**
 * Ask for the packs again: an order found a price other than the one shown,
 * or a pack no longer on sale, so the store shows what is (D-761).
 */
export function useRefreshPacks() {
  const queryClient = useQueryClient();
  return () =>
    void queryClient.invalidateQueries({ queryKey: queryKeys.packs() });
}
