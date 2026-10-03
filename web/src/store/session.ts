import { create } from "zustand";

/**
 * - `unknown`: this page load hasn't finished trying to restore a session.
 * - `signed-in`: there's an access token.
 * - `signed-out`: there's none, and the API said so.
 */
export type SessionStatus = "unknown" | "signed-in" | "signed-out";

type SessionState = {
  /**
   * The 15-minute access JWT. Memory only (D-024): never localStorage, never a
   * URL, so a reload loses it and `/auth/refresh` restores it (T-3.10).
   */
  accessToken: string | null;
  status: SessionStatus;
  /**
   * Restoring failed for a reason that isn't the API's answer (no signal, a
   * 5xx): the session may well exist, so the screens offer a retry rather
   * than send anyone to /login (T-3.10).
   */
  restoreFailed: boolean;
  /** The PIN lock is up. A deterrent, not protection (D-069). */
  locked: boolean;
  /**
   * Whether this page load has decided about the lock. A restored session with
   * a PIN locks once on load; a sign-in by phone just proved the number, so
   * the person isn't asked for a PIN as well.
   */
  lockDecided: boolean;
  signIn: (accessToken: string, options?: { fresh?: boolean }) => void;
  /** Forget the session in this tab. The API's side is `logout()`. */
  signOut: () => void;
  setRestoreFailed: (failed: boolean) => void;
  setLocked: (locked: boolean) => void;
  setLockDecided: () => void;
};

const SIGNED_OUT = {
  accessToken: null,
  status: "signed-out",
  restoreFailed: false,
  locked: false,
  lockDecided: false,
} as const;

/** Who is signed in, for this tab only. The api client reads the token from here. */
export const useSession = create<SessionState>()((set) => ({
  accessToken: null,
  status: "unknown",
  restoreFailed: false,
  locked: false,
  lockDecided: false,
  signIn: (accessToken, options) =>
    set((state) => ({
      accessToken,
      status: "signed-in",
      restoreFailed: false,
      lockDecided: state.lockDecided || options?.fresh === true,
    })),
  signOut: () => set(SIGNED_OUT),
  setRestoreFailed: (restoreFailed) => set({ restoreFailed }),
  setLocked: (locked) => set({ locked }),
  setLockDecided: () => set({ lockDecided: true }),
}));

/** Back to a fresh page load's state. Tests only. */
export function resetSession(): void {
  useSession.setState({ ...SIGNED_OUT, status: "unknown" });
}
