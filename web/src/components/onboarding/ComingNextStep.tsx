import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";

import { StepFrame } from "./StepFrame";

/**
 * The selfie, until T-4.7 builds it: its place in the frame, saying it's next,
 * with the way out. Photos were here too until T-4.6.
 */
export function ComingNextStep() {
  return (
    <StepFrame
      index={12}
      title={t("onboarding.selfie.title")}
      back={stepPath("pin")}
      signedIn
    >
      <p className="text-body text-mute">{t("placeholder.onboardingStep")}</p>
    </StepFrame>
  );
}
