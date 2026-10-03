import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetSession, useSession } from "@/store/session";

import { logout, restoreSession, retryRestore } from "./session";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "./testing/fakeApi";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  clearCookies();
  resetSession();
});

describe("restoring a session on load (T-3.10)", () => {
  it("refreshes once per page load, however many layouts ask", async () => {
    const api_ = fakeApi({
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
    });

    await Promise.all([restoreSession(), restoreSession()]);
    await restoreSession();

    expect(api_.sent()).toEqual(["POST /v1/auth/refresh"]);
    expect(useSession.getState()).toMatchObject({
      accessToken: "t",
      status: "signed-in",
    });
  });

  it("is signed out when the API says there's no session", async () => {
    fakeApi({ "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED") });

    await restoreSession();

    expect(useSession.getState()).toMatchObject({
      status: "signed-out",
      restoreFailed: false,
    });
  });

  it.each([
    ["no signal", () => Promise.reject(new TypeError("Failed to fetch"))],
    ["a 5xx", () => envelope(502, "INTERNAL")],
  ])(
    "after %s stays unknown and offers a retry, never /login",
    async (_, answer) => {
      fakeApi({ "POST /v1/auth/refresh": answer });

      await restoreSession();

      expect(useSession.getState()).toMatchObject({
        status: "unknown",
        restoreFailed: true,
      });
    },
  );

  it("a retry tries again", async () => {
    fakeApi({
      "POST /v1/auth/refresh": () =>
        Promise.reject(new TypeError("Failed to fetch")),
    });
    await restoreSession();

    const api_ = fakeApi({
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
    });
    await retryRestore();

    expect(api_.sent()).toEqual(["POST /v1/auth/refresh"]);
    expect(useSession.getState()).toMatchObject({
      status: "signed-in",
      restoreFailed: false,
    });
  });
});

describe("logout (T-3.10, D-067)", () => {
  it("sends the refresh cookie and X-CSRF, then signs the tab out", async () => {
    useSession.getState().signIn("t");
    const api_ = fakeApi({ "POST /v1/auth/logout": () => json(204) });

    await logout();

    expect(api_.calls).toHaveLength(1);
    expect(api_.calls[0]?.credentials).toBe("include");
    expect(api_.calls[0]?.headers.get("X-CSRF")).toBe("c1");
    expect(useSession.getState().status).toBe("signed-out");
  });

  it("treats a 401 as done: there was no session left to end", async () => {
    useSession.getState().signIn("t");
    fakeApi({ "POST /v1/auth/logout": () => envelope(401, "AUTH_REQUIRED") });

    await logout();

    expect(useSession.getState().status).toBe("signed-out");
  });

  it("stays signed in if the API never heard: the cookies are still there", async () => {
    useSession.getState().signIn("t");
    fakeApi({
      "POST /v1/auth/logout": () =>
        Promise.reject(new TypeError("Failed to fetch")),
    });

    await expect(logout()).rejects.toThrow(TypeError);
    expect(useSession.getState().status).toBe("signed-in");
  });
});
