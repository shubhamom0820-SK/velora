import { create } from "zustand";

type Session = { accessToken: string; userId: string };

type SessionState = {
  /**
   * The 15-minute access JWT. Memory only (D-024): never localStorage, never a
   * URL, so a reload loses it and T-3.10's refresh call restores it.
   */
  accessToken: string | null;
  userId: string | null;
  setSession: (session: Session) => void;
  clearSession: () => void;
};

/** Who is signed in, for this tab only. The api client reads the token from here. */
export const useSession = create<SessionState>()((set) => ({
  accessToken: null,
  userId: null,
  setSession: ({ accessToken, userId }) => set({ accessToken, userId }),
  clearSession: () => set({ accessToken: null, userId: null }),
}));
