import type { ReactNode } from "react";

import { OnboardingGate } from "@/components/session/OnboardingGate";

/** Signed in, onboarding not `done`, and never ahead of the person's step (D-080). */
export default function OnboardingLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <OnboardingGate>{children}</OnboardingGate>;
}
