import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";

import { StepFrame } from "./StepFrame";

/**
 * Photos and the selfie, until Sprint 4 builds them (T-4.6, T-4.7): their
 * place in the frame, saying they're next, with the way out. A real user
 * stops at photos until T-4.3 (D-068).
 */
export function ComingNextStep({ step }: { step: "photos" | "selfie" }) {
  return step === "photos" ? (
    <StepFrame
      index={8}
      title={t("onboarding.photos.title")}
      back={stepPath("about")}
      signedIn
    >
      <p className="text-body text-mute">{t("placeholder.onboardingStep")}</p>
    </StepFrame>
  ) : (
    <StepFrame
      index={11}
      title={t("onboarding.selfie.title")}
      back={stepPath("pin")}
      signedIn
    >
      <p className="text-body text-mute">{t("placeholder.onboardingStep")}</p>
    </StepFrame>
  );
}
