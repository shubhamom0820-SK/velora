import { describe, expect, it } from "vitest";

import {
  dynamicParams,
  generateStaticParams,
} from "@/app/(auth)/onboarding/[step]/page";

import type { components } from "@/types/api";

import {
  isAhead,
  onboardingSlugs,
  placeOf,
  STEP_SLUGS,
  stepForSlug,
  stepPath,
  type OnboardingStep,
  type PendingStep,
} from "./onboarding";

type Me = components["schemas"]["Me"];

// The API's order (02-ARCHITECTURE §5). A copy on purpose: the enum's order
// is a migration, and this test fails if the map's order ever drifts from it.
const API_ORDER: PendingStep[] = [
  "dob",
  "gender",
  "seeking",
  "profile",
  "username",
  "about",
  "photos",
  "interests",
  "pin",
  "selfie",
];

describe("onboarding URLs are D-080's slugs", () => {
  it("are exactly these, one per step, in the API's order, with the location question after Name (D-220)", () => {
    expect(Object.entries(STEP_SLUGS)).toEqual([
      ["dob", "birthday"],
      ["gender", "gender"],
      ["seeking", "looking-for"],
      ["profile", "name"],
      ["location", "location"],
      ["username", "username"],
      ["about", "about"],
      ["photos", "photos"],
      ["interests", "interests"],
      ["pin", "pin"],
      ["selfie", "selfie"],
    ]);
    expect(Object.keys(STEP_SLUGS).filter((k) => k !== "location")).toEqual(
      API_ORDER,
    );
  });

  it("are all different", () => {
    const slugs = onboardingSlugs();
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("are the only onboarding pages there are: any other is a 404", () => {
    expect(generateStaticParams()).toEqual(
      onboardingSlugs().map((step) => ({ step })),
    );
    expect(dynamicParams).toBe(false);
  });

  it("name each step, and only ours", () => {
    for (const step of API_ORDER) {
      expect(stepForSlug(STEP_SLUGS[step])).toBe(step);
    }
    expect(stepForSlug("location")).toBe("location");
    expect(stepForSlug("dob")).toBeNull(); // the enum is never a URL
    expect(stepForSlug("seeking")).toBeNull();
    expect(stepForSlug("")).toBeNull();
  });

  it("send a finished onboarding to the app", () => {
    expect(stepPath("done")).toBe("/discover");
    expect(stepPath("dob")).toBe("/onboarding/birthday");
  });

  it("put later steps ahead and earlier ones behind", () => {
    expect(isAhead("gender", "dob")).toBe(true);
    expect(isAhead("dob", "dob")).toBe(false);
    expect(isAhead("dob", "seeking")).toBe(false);
    expect(isAhead("selfie", "pin")).toBe(true);
    expect(isAhead("selfie", "done")).toBe(false);
    expect(isAhead("location", "profile")).toBe(true);
    expect(isAhead("location", "username")).toBe(false);
    expect(isAhead("username", "location")).toBe(true);
    expect(isAhead("profile", "location")).toBe(false);
  });
});

function me(
  onboarding_step: OnboardingStep,
  location: Me["profile"]["location"],
): Me {
  return { onboarding_step, profile: { location } } as Me;
}

describe("where a person is (D-220)", () => {
  it("is their step up to Name, location or not", () => {
    for (const step of API_ORDER.slice(0, API_ORDER.indexOf("username"))) {
      expect(placeOf(me(step, "none"))).toBe(step);
    }
  });

  it("is the location question past Name, until a location is set", () => {
    for (const step of API_ORDER.slice(API_ORDER.indexOf("username"))) {
      expect(placeOf(me(step, "none"))).toBe("location");
      expect(placeOf(me(step, "fresh"))).toBe(step);
      expect(placeOf(me(step, "stale"))).toBe(step);
    }
  });

  it("is the app once onboarding is done, location or not", () => {
    expect(placeOf(me("done", "none"))).toBe("done");
    expect(stepPath(placeOf(me("username", "none")))).toBe(
      "/onboarding/location",
    );
  });
});
