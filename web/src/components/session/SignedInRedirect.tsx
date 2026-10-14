"use client";

import { placeOf, stepPath } from "@/lib/onboarding";

import { useReplace, useSignedInMe } from "./useSignedInMe";

/**
 * On /login: someone whose session restored goes where they belong, their
 * onboarding screen or the app (T-3.10). /login doesn't wait for the restore:
 * the sign-in screen shows at once, and this moves on only if a session turns
 * up. Only sending a code waits for it (P-850, D-950). Draws nothing.
 */
export function SignedInRedirect() {
  const gate = useSignedInMe();
  useReplace(gate.kind === "ready" ? stepPath(placeOf(gate.me)) : null);
  return null;
}
