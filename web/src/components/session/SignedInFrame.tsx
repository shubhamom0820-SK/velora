"use client";

import type { ReactNode } from "react";

import { LockScreen, usePinLock } from "./PinLock";

/**
 * A signed-in screen with the PIN lock over it when it's up. Behind the lock
 * the page is `inert`: no focus, no clicks, hidden from screen readers.
 */
export function SignedInFrame({
  hasPin,
  children,
}: {
  hasPin: boolean;
  children: ReactNode;
}) {
  const locked = usePinLock(hasPin);
  return (
    <>
      <div inert={locked}>{children}</div>
      {locked && <LockScreen />}
    </>
  );
}
