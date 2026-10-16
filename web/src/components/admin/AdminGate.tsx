"use client";

import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import {
  SessionFailed,
  SessionLoading,
} from "@/components/session/SessionScreens";
import { SignedInFrame } from "@/components/session/SignedInFrame";
import { useReplace, useSignedInMe } from "@/components/session/useSignedInMe";
import type { Me } from "@/lib/queries/me";

/**
 * Who sees the panel: staff, by `Me.role` (T-9.5). An allowlist, so a role
 * added later sees the 404 until someone decides (rule 16).
 */
export const STAFF: ReadonlySet<Me["role"]> = new Set(["moderator", "admin"]);

/**
 * `/admin`: signed in, and staff; anyone else gets the 404 page, as if there
 * were nothing here (replacing T-1.22's `next dev`-only gate, P-30).
 *
 * **UX, never protection** (D-024): anyone can download this page's
 * JavaScript, and the Next.js server never sees a session here. Every
 * `/v1/admin/*` route carries its own `require_role`, the only thing guarding
 * admin data. Staff need not have finished onboarding, so unlike `AppGate`
 * this never sends anyone to a step; the PIN lock covers it as it covers the
 * app.
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const gate = useSignedInMe();
  useReplace(gate.kind === "signed-out" ? "/login" : null);

  if (gate.kind === "failed") return <SessionFailed onRetry={gate.retry} />;
  if (gate.kind !== "ready") return <SessionLoading />;
  if (!STAFF.has(gate.me.role)) notFound();
  return <SignedInFrame hasPin={gate.me.has_pin}>{children}</SignedInFrame>;
}
