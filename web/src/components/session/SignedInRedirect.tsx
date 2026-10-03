"use client";

import { stepPath } from "@/lib/onboarding";

import { useReplace, useSignedInMe } from "./useSignedInMe";

/**
 * On /login: someone whose session restored goes where they belong, their
 * onboarding step or the app (T-3.10). /login doesn't wait for the restore:
 * the sign-in screen shows at once, and this moves on only if a session turns
 * up. Draws nothing.
 */
export function SignedInRedirect() {
  const gate = useSignedInMe();
  useReplace(gate.kind === "ready" ? stepPath(gate.me.onboarding_step) : null);
  return null;
}
