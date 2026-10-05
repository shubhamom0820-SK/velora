// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { en } from "./en";

/**
 * D-262 (T-4.5): no word we publish says a person is verified, real, live, or
 * who they say they are. The selfie is compared with the profile's photos, by
 * a threshold nobody has measured on our users (D-260), and that comparison
 * doesn't stop a man holding a woman's photos and one real selfie of her. A
 * word that promises more is a promise the product can't keep, until P-160
 * measures it, and the founder decides what may be claimed then.
 *
 * Each word below is checked in every string in `en.ts` and the share image's
 * alt text. Two strings use "verify" in a sense that isn't about a person, each
 * named here with why; the list is held exact, so it can't quietly grow.
 */
const CLAIMS: readonly RegExp[] = [
  /verif/i,
  /really you/i,
  /who (?:you|they|she|he) (?:say|are|claim)/i,
  /real (?:person|people|woman|women|man|men)/i,
  /live (?:person|people)/i,
  /liveness/i,
  /genuine/i,
  /authentic/i,
  /guarantee/i,
  /confirm\w* (?:that )?(?:you are|you're|who|your identity|their identity)/i,
];

const ALLOWED: Readonly<Record<string, string>> = {
  // The sign-in code's button: the code is verified, not the person.
  "onboarding.code.verify": "Verify",
  // D-093's Locked words for a rejected photo (a possible minor among them).
  "onboarding.photos.reasons.other":
    "We couldn't verify this photo — try a different one",
};

function strings(value: unknown, path: string[] = []): [string, string][] {
  if (typeof value === "string") return [[path.join("."), value]];
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, inner]) =>
      strings(inner, [...path, key]),
    );
  return [];
}

const ALT = readFileSync(
  join(process.cwd(), "src/app/opengraph-image.alt.txt"),
  "utf8",
);

describe("no published word claims more than a selfie compared (D-262)", () => {
  const all = [...strings(en), ["opengraph-image.alt.txt", ALT] as const];

  it("says none of the claims anywhere but the two named keys", () => {
    const found = all
      .filter(([key]) => !(key in ALLOWED))
      .filter(([, text]) => CLAIMS.some((claim) => claim.test(text)))
      .map(([key, text]) => `${key}: ${text}`);

    expect(found).toEqual([]);
  });

  it("allows exactly the two named strings, word for word", () => {
    const allowed = all.filter(([key]) => key in ALLOWED);

    expect(Object.fromEntries(allowed)).toEqual(ALLOWED);
  });

  it("would catch the four strings it replaced", () => {
    for (const old of [
      "Your selfie, to check that you're really you. It's never shown to anyone.",
      "Verified, moderated",
      "Selfie verification, photo checks, and reports that actually remove people.",
      "Verified",
      "Women verify with a selfie before their profile goes live",
    ])
      expect(CLAIMS.some((claim) => claim.test(old))).toBe(true);
  });

  it("would catch the prototype's selfie screen, which T-4.7 doesn't say", () => {
    // The prototype's words for the selfie step and the profile's line
    // (08-DESIGN's list of where the prototype is wrong, item 14): each
    // claims a person verified.
    for (const old of [
      "Face matched — verified",
      "You're verified",
      "Selfie verified",
      "Optional — but verified profiles get noticeably more replies.",
      "Not verified — you'll get fewer replies",
    ])
      expect(CLAIMS.some((claim) => claim.test(old))).toBe(true);
  });

  it("keeps the sentence that says the team may look", () => {
    // D-264: the founder looks at every selfie until P-160 measures the
    // threshold, so /privacy must say so, and never be softened away; the
    // selfie step says it too, where the selfie is taken (T-4.7).
    expect(en.legal.privacy.collect.selfie).toContain(
      "our team may look at it to check a comparison",
    );
    expect(en.onboarding.selfie.private).toContain(
      "Our team may look at it to check a comparison.",
    );
  });
});
