import type { components } from "@/types/api";

/**
 * Where each onboarding step lives (D-080). A step's URL is a slug of its own,
 * never its `onboarding_t` value: renaming a step changes a key here, never a
 * link. When the API gains a step, `make types` adds it to `OnboardingStep`
 * and this map stops compiling until the step has a slug. The location
 * question has a slug here too, though no step (T-4.10, D-220).
 */

export type OnboardingStep = components["schemas"]["OnboardingStep"];
export type PendingStep = Exclude<OnboardingStep, "done">;
/** An onboarding screen: each step's, and the location question's. */
export type Place = PendingStep | "location";

type Me = components["schemas"]["Me"];

/**
 * In the order the API advances through them (02-ARCHITECTURE §5, D-068),
 * with the location question after Name (D-220).
 */
export const STEP_SLUGS = {
  dob: "birthday",
  gender: "gender",
  seeking: "looking-for",
  profile: "name",
  location: "location",
  username: "username",
  about: "about",
  photos: "photos",
  interests: "interests",
  pin: "pin",
  selfie: "selfie",
} as const satisfies Record<Place, string>;

export type OnboardingSlug = (typeof STEP_SLUGS)[Place];

const PLACES = Object.keys(STEP_SLUGS) as Place[];

/**
 * Where a signed-in person is: the app once onboarding is `done`; the
 * location question once they're past it without a location, which the API
 * says in `Me` (D-220); otherwise their step.
 */
export function placeOf(me: Me): Place | "done" {
  const step = me.onboarding_step;
  if (step === "done") return "done";
  if (me.profile.location === "none" && isAhead(step, "location")) {
    return "location";
  }
  return step;
}

/** A place's URL, or the app's for `done`. */
export function stepPath(place: Place | "done"): string {
  return place === "done" ? "/discover" : `/onboarding/${STEP_SLUGS[place]}`;
}

/** Every onboarding slug, for the route's static params. */
export function onboardingSlugs(): OnboardingSlug[] {
  return PLACES.map((place) => STEP_SLUGS[place]);
}

/** The place a slug names, or null for one that isn't ours. */
export function stepForSlug(slug: string): Place | null {
  return PLACES.find((place) => STEP_SLUGS[place] === slug) ?? null;
}

/**
 * Whether `place` comes after where the person is. A later screen redirects
 * them back to theirs; theirs or an earlier one loads, as an edit (D-068).
 */
export function isAhead(place: Place, current: Place | "done"): boolean {
  if (current === "done") return false;
  return PLACES.indexOf(place) > PLACES.indexOf(current);
}
