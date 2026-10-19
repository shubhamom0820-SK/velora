"use client";

import { useEffect } from "react";

import { register } from "@/lib/push";

/**
 * Registers `/sw.js` on every page, the landing page included (T-9.7,
 * D-1041), once the page has hydrated, so it never competes with the first
 * load. The worker is the push one (T-9.4), never a second: `push.ts` alone
 * touches the service worker. Renders nothing.
 */
export function ServiceWorkerRegistrar() {
  useEffect(() => {
    void register();
  }, []);
  return null;
}
