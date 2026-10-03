import { OnboardingScreen } from "@/components/onboarding/OnboardingScreen";
import { onboardingSlugs } from "@/lib/onboarding";
import { siteUrl } from "@/lib/site";

/** Only D-080's slugs exist; any other is a 404. */
export const dynamicParams = false;

export function generateStaticParams() {
  return onboardingSlugs().map((step) => ({ step }));
}

/** Each onboarding step's screen (T-3.11, T-3.12). */
export default async function OnboardingStepPage({
  params,
}: PageProps<"/onboarding/[step]">) {
  const { step } = await params;
  // The site's own host, for the username's page (`<host>/@name`): read here,
  // at build time, where APP_ENV is.
  return <OnboardingScreen slug={step} host={new URL(siteUrl()).host} />;
}
