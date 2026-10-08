// @vitest-environment node
import { describe, expect, it } from "vitest";

import { en } from "./en";

/**
 * A man asking again within `album_reask_days` of her decline or revoke is
 * refused `recently_declined` (D-731). Its words never say a decline happened
 * nor point at the person (the founder, 9 October 2026, D-790): a "no" must
 * not reach him through the refusal of his next request. Neutral words,
 * naming nobody and no answer.
 */
describe("the album's too-soon refusal (D-790)", () => {
  const words = en.profile.albumTooSoon;

  it("names no decline, refusal or answer", () => {
    expect(words).not.toMatch(
      /declin|refus|reject|turned? (?:you )?down|said no|\bno\b|answer|revok|block/i,
    );
  });

  it("names no person, and has no slot for a name", () => {
    expect(words).not.toMatch(
      /\b(?:she|her|hers|herself|he|him|his|they|them|their|owner|someone)\b/i,
    );
    expect(words).not.toMatch(/[{}]/);
  });

  it("is the founder's words", () => {
    expect(words).toBe("You can't send a request right now. Try again later.");
  });
});
