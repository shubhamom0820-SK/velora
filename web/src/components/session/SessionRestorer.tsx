"use client";

import { useEffect } from "react";

import { restoreSession } from "@/lib/session";

/**
 * Starts restoring the session as a signed-in group's layout mounts (T-3.10):
 * `(auth)`, `(app)` and `/admin` only, never a marketing page. Once per page load, however
 * many layouts mount it. Draws nothing.
 */
export function SessionRestorer() {
  useEffect(() => {
    void restoreSession();
  }, []);
  return null;
}
