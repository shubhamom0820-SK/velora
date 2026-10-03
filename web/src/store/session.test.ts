import { afterEach, describe, expect, it } from "vitest";

import { resetSession, useSession } from "./session";

describe("useSession", () => {
  afterEach(() => {
    resetSession();
  });

  it("starts unknown: the page load hasn't restored a session yet", () => {
    expect(useSession.getState()).toMatchObject({
      accessToken: null,
      status: "unknown",
      restoreFailed: false,
      locked: false,
      lockDecided: false,
    });
  });

  it("holds a token until signed out, and forgets the lock with it", () => {
    useSession.getState().signIn("jwt");
    useSession.getState().setLocked(true);
    expect(useSession.getState()).toMatchObject({
      accessToken: "jwt",
      status: "signed-in",
    });

    useSession.getState().signOut();
    expect(useSession.getState()).toMatchObject({
      accessToken: null,
      status: "signed-out",
      locked: false,
      lockDecided: false,
    });
  });

  it("decides the lock already for a fresh sign-in, not for a restore", () => {
    useSession.getState().signIn("jwt");
    expect(useSession.getState().lockDecided).toBe(false);

    resetSession();
    useSession.getState().signIn("jwt", { fresh: true });
    expect(useSession.getState().lockDecided).toBe(true);
  });

  it("clears a failed restore once a token arrives", () => {
    useSession.getState().setRestoreFailed(true);
    useSession.getState().signIn("jwt");
    expect(useSession.getState().restoreFailed).toBe(false);
  });
});
