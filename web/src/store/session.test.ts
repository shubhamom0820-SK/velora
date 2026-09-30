import { afterEach, describe, expect, it } from "vitest";

import { useSession } from "./session";

describe("useSession", () => {
  afterEach(() => {
    useSession.getState().clearSession();
  });

  it("starts signed out", () => {
    expect(useSession.getState()).toMatchObject({
      accessToken: null,
      userId: null,
    });
  });

  it("holds a session until it is cleared", () => {
    useSession.getState().setSession({ accessToken: "jwt", userId: "u1" });
    expect(useSession.getState()).toMatchObject({
      accessToken: "jwt",
      userId: "u1",
    });

    useSession.getState().clearSession();
    expect(useSession.getState()).toMatchObject({
      accessToken: null,
      userId: null,
    });
  });
});
