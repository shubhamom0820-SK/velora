"use client";

import { useReplace, useSignedInMe } from "@/components/session/useSignedInMe";
import { useProfileByUsername } from "@/lib/queries/profiles";

/**
 * On `/@username`: someone signed in, onboarding done, goes to the in-app
 * profile, `/people/[id]` (T-6.8), whatever the public link says; the API
 * decides whether they may see it. Draws nothing.
 */
export function SignedInProfileRedirect({ username }: { username: string }) {
  const gate = useSignedInMe();
  const ready = gate.kind === "ready" && gate.me.onboarding_step === "done";
  const found = useProfileByUsername(username, ready);
  useReplace(found.data ? `/people/${found.data.id}` : null);
  return null;
}
