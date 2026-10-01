/*
 * Compile-time checks for t(), run by `pnpm typecheck` (tsc). Never imported,
 * so never bundled. The runtime behaviour is tested in t.test.ts.
 */
import { t } from "./t";

export function typeChecks(): void {
  t("placeholder.login");
  t("landing.join", { app: "Velora" });

  // @ts-expect-error — a key that isn't in en.ts must not compile.
  t("placeholder.nope");

  // @ts-expect-error — a branch is not a string.
  t("placeholder");
}
