/*
 * Compile-time checks for t(), run by `pnpm typecheck` (tsc). Never imported,
 * so never bundled. The runtime behaviour is tested in t.test.ts.
 */
import type { components } from "@/types/api";

import type { en } from "./en";
import { t } from "./t";

type LedgerReason = components["schemas"]["LedgerReason"];

/** `true` only when A and B are the same set of keys. */
type SameKeys<A, B> = [A] extends [B]
  ? [B] extends [A]
    ? true
    : false
  : false;

export function typeChecks(): void {
  t("placeholder.login");
  t("landing.join", { app: "Velora" });

  // @ts-expect-error — a key that isn't in en.ts must not compile.
  t("placeholder.nope");

  // @ts-expect-error — a branch is not a string.
  t("placeholder");

  // T-5.5: the history's words cover exactly the API's ledger reasons. This
  // holds even if someone drops the `satisfies` beside them in en.ts.
  const everyReasonHasWords: SameKeys<
    keyof typeof en.wallet.reason,
    LedgerReason
  > = true;
  void everyReasonHasWords;

  // So any reason the API sends has a key, built from the enum.
  const reason = "thread_open" as LedgerReason;
  t(`wallet.reason.${reason}`);
}
