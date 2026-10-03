import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { logout } from "@/lib/session";

/**
 * Sign out (T-3.10). Afterwards nobody's data stays in the cache, and the
 * screens' gates send the tab to /login.
 */
export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.clear(),
  });
}

/**
 * Check the PIN behind the lock screen (D-069). 204 when right; `PIN_INVALID`
 * with `attempts_left` or `reset_required`; `SESSION_REVOKED` at the fifth
 * wrong one, which the api client turns into a signed-out tab.
 */
export function useVerifyPin() {
  return useMutation({
    mutationFn: (pin: string) =>
      api.post("/v1/auth/pin/verify", { body: { pin } }),
  });
}
