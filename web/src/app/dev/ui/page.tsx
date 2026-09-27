import { notFound } from "next/navigation";

import { UiGallery } from "./UiGallery";

/**
 * Every primitive in every state (T-1.19). An allowlist: only `next dev`
 * serves it, so production, Vercel previews and tests all get a 404. Its demo
 * copy is inline on purpose — en.ts holds what users see, and this page never
 * reaches them. No `metadata` export: Next resolves it even for a 404, so it
 * would leak into production.
 */
export default function DevUiPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <UiGallery />;
}
