import { en } from "@/i18n/en";

/**
 * A catalogue entry's words, from `en.ts` by its id (P-26), never the API's
 * label: an id `en.ts` doesn't know yet shows nothing rather than a raw label.
 */
export function intentLabel(id: number): string | null {
  const labels: Readonly<Record<string, string>> = en.intents;
  return labels[String(id)] ?? null;
}

export function interestLabel(id: number): string | null {
  const labels: Readonly<Record<string, string>> = en.interests;
  return labels[String(id)] ?? null;
}

/** The four kudos, in the kinds' own order (D-007, D-680). */
export const KUDOS = [
  "great_conversation",
  "genuinely_funny",
  "easy_to_talk_to",
  "really_thoughtful",
] as const;
