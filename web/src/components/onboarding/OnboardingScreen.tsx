"use client";

import { stepForSlug } from "@/lib/onboarding";
import { useMe } from "@/lib/queries/me";

import { AboutStep } from "./AboutStep";
import { BirthdayStep } from "./BirthdayStep";
import { ComingNextStep } from "./ComingNextStep";
import { GenderStep } from "./GenderStep";
import { InterestsStep } from "./InterestsStep";
import { LookingForStep } from "./LookingForStep";
import { NameStep } from "./NameStep";
import { PhotosStep } from "./PhotosStep";
import { PinStep } from "./PinStep";
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
    case "about":
      return <AboutStep me={me} />;
    case "photos":
      return <PhotosStep me={me} />;
    case "interests":
      return <InterestsStep me={me} />;
    case "pin":
      return <PinStep me={me} />;
    case "selfie":
      return <ComingNextStep />;
    case null:
      return null;
  }
}
