import { describe, expect, it } from "vitest";

import {
  dynamicParams,
  generateStaticParams,
} from "@/app/(auth)/onboarding/[step]/page";

import {
  isAhead,
  onboardingSlugs,
  STEP_SLUGS,
  stepForSlug,
  stepPath,
  type PendingStep,
} from "./onboarding";

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
  it("are exactly these, one per step, in the API's order", () => {
    expect(Object.entries(STEP_SLUGS)).toEqual([
      ["dob", "birthday"],
      ["gender", "gender"],
      ["seeking", "looking-for"],
      ["profile", "name"],
      ["username", "username"],
      ["about", "about"],
      ["photos", "photos"],
      ["interests", "interests"],
      ["pin", "pin"],
      ["selfie", "selfie"],
    ]);
    expect(Object.keys(STEP_SLUGS)).toEqual(API_ORDER);
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
  });
});
