"use client";

import { type RefObject, useEffect, useState } from "react";

import { type FirebasePhoneSignIn, startFirebaseSignIn } from "@/lib/firebase";

/**
 * This screen's Firebase (T-3.14): started when the screen mounts, into
 * `container`, and taken down when it goes. Null until it has started, and if
 * it never does (its script blocked or offline), sending says so.
 */
export function useFirebasePhone(
  container: RefObject<HTMLElement | null>,
): FirebasePhoneSignIn | null {
  const [firebase, setFirebase] = useState<FirebasePhoneSignIn | null>(null);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    let live = true;
    let started: FirebasePhoneSignIn | null = null;
    startFirebaseSignIn(element).then(
      (signIn) => {
        if (live) {
          started = signIn;
          setFirebase(signIn);
        } else {
          signIn.dispose();
        }
      },
      () => undefined,
    );
    return () => {
      live = false;
      started?.dispose();
    };
  }, [container]);
  return firebase;
}
