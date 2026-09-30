"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";

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
  return new QueryClient({
    defaultOptions: { queries: { retry: shouldRetry } },
  });
}

/** Server state for the whole app. Mounted once, in the root layout. */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
