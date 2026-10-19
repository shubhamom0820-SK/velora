"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useMe } from "@/lib/queries/me";

/**
 * The socket's client and the events it applies, fetched as the app mounts
 * rather than in its first load (T-9.10, D-1035): with their schemas, zod's
 * core among them, they were 27 KB gzipped of every `(app)` page, and the
 * socket waits for the gate anyway. The conversation screen still imports
 * `@/lib/ws` itself for typing, so its page loads it at once, as before.
 */
function loadSocket() {
  return Promise.all([import("@/lib/ws"), import("@/lib/queries/realtime")]);
}

/**
 * The app's socket (T-7.12), open while someone signed in and onboarded is
 * inside the app: mounted in `(app)`'s layout, under `AppGate`, so signing out
 * unmounts it and closes the socket. Draws nothing. Left before its client has
 * loaded, it opens nothing.
 */
export function Realtime() {
  const client = useQueryClient();
  const gender = useMe().data?.gender ?? undefined;
  // Read by each event as it arrives, so a socket never restarts for it.
  const genderRef = useRef(gender);
  useEffect(() => {
    genderRef.current = gender;
  }, [gender]);

  useEffect(() => {
    let left = false;
    let close = () => {};
    void loadSocket().then(([ws, realtime]) => {
      if (left) return;
      const socket = new ws.Realtime({
        onEvent: (event) =>
          realtime.applyEvent(client, event, genderRef.current),
        onReconnect: () => realtime.afterReconnect(client),
      });
      ws.setCurrentRealtime(socket);
      socket.start();
      close = () => {
        ws.setCurrentRealtime(null);
        socket.stop();
      };
    });
    return () => {
      left = true;
      close();
    };
  }, [client]);

  return null;
}
