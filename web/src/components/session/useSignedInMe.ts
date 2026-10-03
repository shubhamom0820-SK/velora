"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useMe, type Me } from "@/lib/queries/me";
import { retryRestore } from "@/lib/session";
import { useSession } from "@/store/session";

export type SignedInGate =
  | { kind: "waiting" }
  | { kind: "failed"; retry: () => void }
  | { kind: "signed-out" }
  | { kind: "ready"; me: Me };

/**
 * Where a screen that needs a session stands: still restoring, failed for a
 * reason that isn't the API's answer, signed out, or signed in with `Me`.
 */
export function useSignedInMe(): SignedInGate {
  const status = useSession((state) => state.status);
  const restoreFailed = useSession((state) => state.restoreFailed);
  const me = useMe();

  if (status === "signed-out") return { kind: "signed-out" };
  if (status === "unknown") {
    return restoreFailed
      ? { kind: "failed", retry: () => void retryRestore() }
      : { kind: "waiting" };
  }
  if (me.data) return { kind: "ready", me: me.data };
  if (me.isError) return { kind: "failed", retry: () => void me.refetch() };
  return { kind: "waiting" };
}

/** Replace the current URL with `target` once it's known. */
export function useReplace(target: string | null): void {
  const router = useRouter();
  useEffect(() => {
    if (target !== null) router.replace(target);
  }, [router, target]);
}
