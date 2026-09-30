/*
 * Compile-time checks for the api client, run by `pnpm typecheck` (tsc). Never
 * imported, so never bundled. The runtime behaviour is tested in api.test.ts.
 */
import { api } from "./api";

export async function typeChecks(): Promise<void> {
  const health = await api.get("/healthz");
  const ok: "ok" = health.status;
  void ok;

  const ready = await api.get("/readyz");
  const database: "ok" | "fail" = ready.checks.database;
  void database;

  // @ts-expect-error — a path the API doesn't have must not compile.
  await api.get("/nope");

  // @ts-expect-error — /healthz has no POST.
  await api.post("/healthz");
}
