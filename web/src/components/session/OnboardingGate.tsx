"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { isAhead, placeOf, stepForSlug, stepPath } from "@/lib/onboarding";

import { SessionFailed, SessionLoading } from "./SessionScreens";
import { SignedInFrame } from "./SignedInFrame";
import { useReplace, useSignedInMe } from "./useSignedInMe";

/**
 * The onboarding routes (T-3.10, D-080): signed in, onboarding not `done`. A
 * screen after the person's sends them back to theirs, the location question
 * included (D-220); theirs or an earlier one loads, as an edit (D-068). Signed
 * out goes to /login, `done` to the app.
 */
export function OnboardingGate({ children }: { children: ReactNode }) {
  const gate = useSignedInMe();
  const pathname = usePathname();
  const place = stepForSlug(pathname.split("/").at(-1) ?? "");

  let target: string | null = null;
  if (gate.kind === "signed-out") target = "/login";
  else if (gate.kind === "ready") {
    const current = placeOf(gate.me);
    if (current === "done") target = stepPath("done");
    else if (place !== null && isAhead(place, current))
      target = stepPath(current);
  }
  useReplace(target);

  if (gate.kind === "failed") return <SessionFailed onRetry={gate.retry} />;
  if (gate.kind !== "ready" || target !== null) return <SessionLoading />;
  return <SignedInFrame hasPin={gate.me.has_pin}>{children}</SignedInFrame>;
}
