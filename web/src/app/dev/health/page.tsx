import { notFound } from "next/navigation";

import { HealthCheck } from "./HealthCheck";

/**
 * Proves the data layer end to end (T-1.18): `/healthz` through a query hook,
 * the api client and the browser's CORS check. Same allowlist as `/dev/ui`:
 * only `next dev` serves it. No `metadata` export — Next resolves it even for
 * a 404, so it would leak into production. Its copy is inline, as dev pages'
 * is; en.ts holds what users see.
 */
export default function DevHealthPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <HealthCheck />;
}
