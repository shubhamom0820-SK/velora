// @vitest-environment node
import { describe, expect, it } from "vitest";

import { en } from "./en";

function strings(value: unknown, path: string[] = []): [string, string][] {
  if (typeof value === "string") return [[path.join("."), value]];
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, inner]) =>
      strings(inner, [...path, key]),
    );
  return [];
}

/**
 * Referrals are paused (D-840, P-740): while they are, the web offers no
 * referral code field, no invite or share card, and no copy offering a
 * referral (T-8.8). Every string mentioning one is named here with why, and
 * the list is held exact, so an offer can't arrive unnoticed. Turning
 * referrals back on is a decision of its own, after P-591.
 */
const ALLOWED: Readonly<Record<string, string>> = {
  // The wallet history's word for a reward paid before the pause (T-5.5): a
  // record of the past, never an offer.
  "wallet.reason.referral_reward": "Referral reward",
};

describe("no word offers a referral while they are paused (D-840)", () => {
  it("mentions referring or inviting only in the named keys", () => {
    const found = Object.fromEntries(
      strings(en).filter(([, words]) => /\brefer|\binvit/i.test(words)),
    );

    expect(found).toEqual(ALLOWED);
  });
});
