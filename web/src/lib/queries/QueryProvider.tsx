"use client";

import {
  MutationCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { useStoreSheet } from "@/store/store-sheet";

import { queryKeys } from "./keys";

/**
 * What a mutation can say about itself (TanStack's `meta`, typed here).
 * `touchesWallet`: it spends or credits Velas, so the balance and history are
 * asked again when it settles, whether it succeeded or not: a request that
 * timed out may still have been charged (T-5.5).
 */
type MutationMeta = { touchesWallet?: boolean };

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: MutationMeta;
  }
}

const MAX_RETRIES = 2;

/**
 * A 4xx is the API's answer, not a blip, so retrying can't change it. A 5xx or
 * a network failure retries twice. Mutations keep TanStack's default of no
 * retries: a retried payment is a double charge.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < MAX_RETRIES;
}

export function makeQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    // Mutations only: a query is never refused for want of Velas, and if one
    // were, reading something must not throw a store in anyone's face.
    mutationCache: new MutationCache({
      onError: (error) => {
        if (!(error instanceof ApiError)) return;
        if (error.code !== "INSUFFICIENT_CREDITS") return;
        // The balance shown was more than the API holds: ask again.
        void client.invalidateQueries({ queryKey: queryKeys.wallet() });
        useStoreSheet.getState().show();
      },
      onSettled: (_data, _error, _variables, _result, mutation) => {
        if (!mutation.meta?.touchesWallet) return;
        void client.invalidateQueries({ queryKey: queryKeys.wallet() });
      },
    }),
    defaultOptions: { queries: { retry: shouldRetry } },
  });
  return client;
}

/** Server state for the whole app. Mounted once, in the root layout. */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
