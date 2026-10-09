"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useMe } from "@/lib/queries/me";
import { afterReconnect, applyEvent } from "@/lib/queries/realtime";
import { Realtime as Socket, setCurrentRealtime } from "@/lib/ws";

/**
 * The app's socket (T-7.12), open while someone signed in and onboarded is
 * inside the app: mounted in `(app)`'s layout, under `AppGate`, so signing out
 * unmounts it and closes the socket. Draws nothing.
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
    const socket = new Socket({
      onEvent: (event) => applyEvent(client, event, genderRef.current),
      onReconnect: () => afterReconnect(client),
    });
    setCurrentRealtime(socket);
    socket.start();
    return () => {
      setCurrentRealtime(null);
      socket.stop();
    };
  }, [client]);

  return null;
}
