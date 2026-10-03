"use client";

import { SignOutButton } from "@/components/session/SignOutButton";
import { t } from "@/i18n/t";
import { stepForSlug } from "@/lib/onboarding";
import { useMe } from "@/lib/queries/me";

import { BirthdayStep } from "./BirthdayStep";
import { GenderStep } from "./GenderStep";
import { LookingForStep } from "./LookingForStep";
import { NameStep } from "./NameStep";
import { UsernameStep } from "./UsernameStep";

/**
 * The screen for an onboarding URL (D-080). `OnboardingGate` has already made
 * sure there's a session, `Me`, and that this step isn't ahead of the person's.
 */
export function OnboardingScreen({
  slug,
  host,
}: {
  slug: string;
  host: string;
}) {
  const me = useMe().data;
  if (!me) return null;
  switch (stepForSlug(slug)) {
    case "dob":
      return <BirthdayStep me={me} />;
    case "gender":
      return <GenderStep me={me} />;
    case "seeking":
      return <LookingForStep me={me} />;
    case "profile":
      return <NameStep me={me} />;
    case "username":
      return <UsernameStep me={me} host={host} />;
    default:
      // T-3.12 builds about, interests and the PIN; Sprint 4 photos and the selfie.
      return (
        <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-6 p-6">
          <h1 className="text-title-1">{t("placeholder.onboardingStep")}</h1>
          <SignOutButton />
        </main>
      );
  }
}
