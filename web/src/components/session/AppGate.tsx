"use client";

import type { ReactNode } from "react";

import { LocationRefresh } from "@/components/location/LocationRefresh";
import { placeOf, stepPath } from "@/lib/onboarding";

import { SessionFailed, SessionLoading } from "./SessionScreens";
import { SignedInFrame } from "./SignedInFrame";
import { useReplace, useSignedInMe } from "./useSignedInMe";

/**
 * The `(app)` routes: signed in, and onboarding `done` (T-3.10). Signed out goes
 * to /login, an unfinished onboarding to its step. T-5.6 adds the header and
 * nav inside this, never replacing it (decided planning T-3.10 to T-3.13).
 * Opening it refreshes a stale location, if the browser allows (T-4.10).
 */
export function AppGate({ children }: { children: ReactNode }) {
  const gate = useSignedInMe();
  const target =
    gate.kind === "signed-out"
      ? "/login"
      : gate.kind === "ready" && gate.me.onboarding_step !== "done"
        ? stepPath(placeOf(gate.me))
        : null;
  useReplace(target);

  if (gate.kind === "failed") return <SessionFailed onRetry={gate.retry} />;
  if (gate.kind !== "ready" || target !== null) return <SessionLoading />;
  return (
    <SignedInFrame hasPin={gate.me.has_pin}>
      {children}
      <LocationRefresh me={gate.me} />
    </SignedInFrame>
  );
}
