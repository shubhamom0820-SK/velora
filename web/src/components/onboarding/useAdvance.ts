"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";

/**
 * After a step is saved, go where the person now is: the next step, or back to
 * their own after editing an earlier one (D-068). Pushed, so the browser's back
 * button returns to the screen just left.
 */
export function useAdvance(): (me: Me) => void {
  const router = useRouter();
  return useCallback(
    (me: Me) => router.push(stepPath(me.onboarding_step)),
    [router],
  );
}
