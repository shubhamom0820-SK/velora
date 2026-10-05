"use client";

import { useEffect, useRef } from "react";

import { currentPosition, locationPermission } from "@/lib/geolocation";
import type { Me } from "@/lib/queries/me";
import { useSetLocation } from "@/lib/queries/onboarding";

/**
 * When the app opens, a location the server calls `stale`, over 6 hours old
 * by its own clock, is refreshed (T-4.10, D-220): only if the browser already
 * allows it, so never a prompt, and once per open. Anything that goes wrong is
 * silent: the old location stands, and the next open tries again. Draws
 * nothing.
 */
export function LocationRefresh({ me }: { me: Me }) {
  const { mutate } = useSetLocation();
  const stale = me.profile.location === "stale";
  const tried = useRef(false);

  useEffect(() => {
    if (!stale || tried.current) return;
    tried.current = true;
    void (async () => {
      if ((await locationPermission()) !== "granted") return;
      try {
        mutate(await currentPosition());
      } catch {
        // No reading this time: the old location stands.
      }
    })();
  }, [stale, mutate]);

  return null;
}
