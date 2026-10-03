import { SignOutButton } from "@/components/session/SignOutButton";
import { t } from "@/i18n/t";
import { onboardingSlugs } from "@/lib/onboarding";

/** Only D-080's slugs exist; any other is a 404. */
export const dynamicParams = false;

export function generateStaticParams() {
  return onboardingSlugs().map((step) => ({ step }));
}

/** Placeholder until T-3.11 and T-3.12 build each step's screen. */
export default function OnboardingStepPage() {
  return (
    <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-title-1">{t("placeholder.onboardingStep")}</h1>
      <SignOutButton />
    </main>
  );
}
