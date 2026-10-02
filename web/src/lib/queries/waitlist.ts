import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/types/api";

export type WaitlistJoin = components["schemas"]["WaitlistJoin"];

/**
 * Joins the waitlist (T-2.3). The API answers a repeated email exactly as a new
 * one (D-057), so success says nothing about who else is on the list.
 */
export function useJoinWaitlist() {
  return useMutation({
    mutationFn: (body: WaitlistJoin) => api.post("/v1/waitlist", { body }),
  });
}
