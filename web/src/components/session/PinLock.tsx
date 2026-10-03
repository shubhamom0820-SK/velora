"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { PinPad } from "@/components/ui/PinPad";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { ApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queries/keys";
import { useVerifyPin } from "@/lib/queries/session";
import { useSession } from "@/store/session";

import { SignOutButton } from "./SignOutButton";

/**
 * After this long hidden, the lock comes back (T-3.10). A named constant, not
 * an `app_config` value: a Checklist A exception recorded on T-3.10, because a
 * deterrent the browser runs is not a limit the server enforces (D-069).
 */
export const RELOCK_AFTER_HIDDEN_MS = 5 * 60 * 1000;

/**
 * Whether the PIN lock is up, deciding it once per page load: a restored
 * session with a PIN starts locked, and comes back locked after five minutes
 * hidden. A deterrent for whoever picks up an unlocked phone, not protection:
 * the access token is still in memory behind it (D-069).
 */
export function usePinLock(hasPin: boolean): boolean {
  const locked = useSession((state) => state.locked);
  const lockDecided = useSession((state) => state.lockDecided);

  useEffect(() => {
    if (lockDecided) return;
    const session = useSession.getState();
    session.setLockDecided();
    if (hasPin) session.setLocked(true);
  }, [hasPin, lockDecided]);

  const hiddenAt = useRef<number | null>(null);
  useEffect(() => {
    if (!hasPin) return;
    function onVisibility() {
      if (document.hidden) {
        hiddenAt.current = Date.now();
        return;
      }
      const since = hiddenAt.current;
      hiddenAt.current = null;
      if (since !== null && Date.now() - since >= RELOCK_AFTER_HIDDEN_MS) {
        useSession.getState().setLocked(true);
      }
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [hasPin]);

  return hasPin && locked;
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "PIN_INVALID") {
      if (error.details?.reset_required === true)
        return t("lock.resetRequired");
      const left = error.details?.attempts_left;
      if (typeof left === "number") {
        return left === 1
          ? t("lock.wrongOne")
          : t("lock.wrongMany", { count: left });
      }
    }
    if (error.code === "RATE_LIMITED") return t("lock.tooFast");
  }
  return t("lock.failed");
}

/** The lock screen (08-DESIGN ✦): black, over everything. */
export function LockScreen() {
  const [pin, setPin] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [resetRequired, setResetRequired] = useState(false);
  const verify = useVerifyPin();
  const queryClient = useQueryClient();

  function submit(value: string) {
    verify.mutate(value, {
      onSuccess: () => {
        setPin("");
        setMessage(null);
        useSession.getState().setLocked(false);
      },
      onError: (error) => {
        setPin("");
        // No PIN on the account any more: nothing to unlock with.
        if (error instanceof ApiError && error.code === "NOT_ALLOWED") {
          useSession.getState().setLocked(false);
          void queryClient.invalidateQueries({ queryKey: queryKeys.me() });
          return;
        }
        // SESSION_REVOKED, the fifth wrong PIN, has signed the tab out in the
        // api client; the screen's gate takes it to /login.
        if (
          error instanceof ApiError &&
          error.details?.reset_required === true
        ) {
          setResetRequired(true);
        }
        setMessage(messageFor(error));
      },
    });
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="pin-lock-title"
      className="bg-chrome fixed inset-0 z-50 flex flex-col items-center justify-center px-8"
    >
      <Icon icon={Lock} size={26} className="text-chrome-accent" />
      <h1 id="pin-lock-title" className="text-title-2 text-chrome-ink mt-3.5">
        {t("lock.title")}
      </h1>
      <p
        role={message ? "alert" : undefined}
        className={
          message
            ? "text-small text-chrome-accent mt-1.5 mb-6 text-center"
            : "text-small text-chrome-mute mt-1.5 mb-6 text-center"
        }
      >
        {message ?? t("lock.locked", { app: APP_NAME })}
      </p>
      <PinPad
        tone="chrome"
        value={pin}
        onChange={(value) => {
          setPin(value);
          if (!resetRequired) setMessage(null);
        }}
        onComplete={submit}
        disabled={verify.isPending || resetRequired}
      />
      <div className="mt-8">
        <SignOutButton tone="chrome" label={t("lock.forgot")} />
      </div>
    </div>
  );
}
