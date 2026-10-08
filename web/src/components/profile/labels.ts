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
