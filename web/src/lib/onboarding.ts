import type { components } from "@/types/api";

/**
 * Where each onboarding step lives (D-080). A step's URL is a slug of its own,
 * never its `onboarding_t` value: renaming a step changes a key here, never a
 * link. When the API gains a step, `make types` adds it to `OnboardingStep`
 * and this map stops compiling until the step has a slug.
 */

export type OnboardingStep = components["schemas"]["OnboardingStep"];
export type PendingStep = Exclude<OnboardingStep, "done">;

/** In the order the API advances through them (02-ARCHITECTURE §5, D-068). */
export const STEP_SLUGS = {
  dob: "birthday",
  gender: "gender",
  seeking: "looking-for",
  profile: "name",
  username: "username",
  about: "about",
  photos: "photos",
  interests: "interests",
  pin: "pin",
  selfie: "selfie",
} as const satisfies Record<PendingStep, string>;

export type OnboardingSlug = (typeof STEP_SLUGS)[PendingStep];

const STEPS = Object.keys(STEP_SLUGS) as PendingStep[];

/** Where a signed-in person belongs: their step, or the app once it's `done`. */
export function stepPath(step: OnboardingStep): string {
  return step === "done" ? "/discover" : `/onboarding/${STEP_SLUGS[step]}`;
}

/** Every onboarding slug, for the route's static params. */
export function onboardingSlugs(): OnboardingSlug[] {
  return STEPS.map((step) => STEP_SLUGS[step]);
}

/** The step a slug names, or null for one that isn't ours. */
export function stepForSlug(slug: string): PendingStep | null {
  return STEPS.find((step) => STEP_SLUGS[step] === slug) ?? null;
}

/**
 * Whether `step` comes after where the person is. A later step's screen
 * redirects them back to theirs; theirs or an earlier one loads, as an edit
 * (D-068).
 */
export function isAhead(step: PendingStep, current: OnboardingStep): boolean {
  if (current === "done") return false;
  return STEPS.indexOf(step) > STEPS.indexOf(current);
}
