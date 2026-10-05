import { t } from "@/i18n/t";

/**
 * Velas as users read them (D-049). The API and code keep the neutral name
 * `credits`; only the words say Velas, so a rename touches `en.ts` alone.
 */

const grouping = new Intl.NumberFormat("en-IN");

/** A count with India's grouping: 1,250 and 1,25,000. */
export function creditsCount(count: number): string {
  return grouping.format(count);
}

/** "1 Vela", "5 Velas": the number first (08-DESIGN §6). */
export function creditsText(count: number): string {
  return t(count === 1 ? "wallet.velas.one" : "wallet.velas.other", {
    count: creditsCount(count),
  });
}

/** The unit alone, beside a number drawn on its own. */
export function creditsUnit(count: number): string {
  return t(count === 1 ? "wallet.unit.one" : "wallet.unit.other");
}

/** A change to the balance, signed: "+30", "−5" (a minus sign, not a hyphen). */
export function deltaText(delta: number): string {
  return `${delta < 0 ? "−" : "+"}${creditsCount(Math.abs(delta))}`;
}
