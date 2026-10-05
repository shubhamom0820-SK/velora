"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { placeOf, stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";

/**
 * After a step is saved, go where the person now is: the next screen, or back
 * to their own after editing an earlier one (D-068), the location question
 * included (D-220). Pushed, so the browser's back button returns to the screen
 * just left.
 */
export function useAdvance(): (me: Me) => void {
  const router = useRouter();
  return useCallback((me: Me) => router.push(stepPath(placeOf(me))), [router]);
}
