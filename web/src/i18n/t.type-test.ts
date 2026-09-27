/*
 * Compile-time checks for t(), run by `pnpm typecheck` (tsc). Never imported,
 * so never bundled. Unit tests join with vitest in T-1.19.
 */
import { t } from "./t";

export function typeChecks(): void {
  t("placeholder.login");
  t("placeholder.marketing", { app: "Velora" });

  // @ts-expect-error — a key that isn't in en.ts must not compile.
  t("placeholder.nope");

  // @ts-expect-error — a branch is not a string.
  t("placeholder");
}
