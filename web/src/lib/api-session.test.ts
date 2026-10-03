import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetSession, useSession } from "@/store/session";

import { api, ApiError, REFRESH_LOCK, refreshAccessToken } from "./api";
import {
  clearCookies,
  envelope,
  fakeApi,
  fakeLocks,
  json,
  setCookie,
} from "./testing/fakeApi";

const ME = { id: "u1", onboarding_step: "done" };

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

describe("cookies go only to the refresh cookie's path (T-3.10, D-054)", () => {
  it("sends credentials to /v1/auth/* and none anywhere else", async () => {
    const api_ = fakeApi({
      "GET /healthz": () => json(200, { status: "ok" }),
      "GET /v1/me": () => json(200, ME),
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
      "POST /v1/auth/logout": () => json(204),
    });

    await api.get("/healthz");
    await api.get("/v1/me");
    await api.post("/v1/auth/refresh");
    await api.post("/v1/auth/logout");

    // Every call's value, not "some call included it".
    expect(api_.calls.map((c) => [c.path, c.credentials])).toEqual([
      ["/healthz", "omit"],
      ["/v1/me", "omit"],
      ["/v1/auth/refresh", "include"],
      ["/v1/auth/logout", "include"],
    ]);
  });
});

describe("an expired access token is renewed once, then the request retried", () => {
  it("refreshes and retries with the new token", async () => {
    useSession.getState().signIn("old");
    const api_ = fakeApi({
      "GET /v1/me": (call) =>
        call.headers.get("Authorization") === "Bearer new"
          ? json(200, ME)
          : envelope(401, "TOKEN_EXPIRED"),
      "POST /v1/auth/refresh": () => json(200, { access_token: "new" }),
    });

    await expect(api.get("/v1/me")).resolves.toEqual(ME);
    expect(api_.sent()).toEqual([
      "GET /v1/me",
      "POST /v1/auth/refresh",
      "GET /v1/me",
    ]);
    expect(useSession.getState()).toMatchObject({
      accessToken: "new",
      status: "signed-in",
    });
  });

  it("retries only once: a second expiry ends the session", async () => {
    useSession.getState().signIn("old");
    // Expired three times, then fine: a client that kept retrying would get
    // through on the fourth call, so it fails here instead of hanging.
    let meCalls = 0;
    const api_ = fakeApi({
      "GET /v1/me": () =>
        ++meCalls <= 3 ? envelope(401, "TOKEN_EXPIRED") : json(200, ME),
      "POST /v1/auth/refresh": () => json(200, { access_token: "new" }),
    });

    const error = await api.get("/v1/me").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("TOKEN_EXPIRED");
    expect(api_.sent()).toEqual([
      "GET /v1/me",
      "POST /v1/auth/refresh",
      "GET /v1/me",
    ]);
    expect(useSession.getState().status).toBe("signed-out");
  });

  it("shares one refresh between requests that expire together", async () => {
    useSession.getState().signIn("old");
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const api_ = fakeApi({
      "GET /v1/me": (call) =>
        call.headers.get("Authorization") === "Bearer new"
          ? json(200, ME)
          : envelope(401, "TOKEN_EXPIRED"),
      "POST /v1/auth/refresh": async () => {
        await gate;
        return json(200, { access_token: "new" });
      },
    });

    const both = Promise.all([api.get("/v1/me"), api.get("/v1/me")]);
    // Let both requests fail and ask for a refresh before it answers.
    await vi.waitFor(() =>
      expect(api_.sent().filter((s) => s === "GET /v1/me")).toHaveLength(2),
    );
    release();
    await both;

    expect(
      api_.sent().filter((s) => s === "POST /v1/auth/refresh"),
    ).toHaveLength(1);
  });

  it("renews for a token-authenticated /v1/auth path too, the PIN check", async () => {
    useSession.getState().signIn("old");
    const api_ = fakeApi({
      "POST /v1/auth/pin/verify": (call) =>
        call.headers.get("Authorization") === "Bearer new"
          ? json(204)
          : envelope(401, "TOKEN_EXPIRED"),
      "POST /v1/auth/refresh": () => json(200, { access_token: "new" }),
    });

    await api.post("/v1/auth/pin/verify", { body: { pin: "4829" } });

    expect(api_.sent()).toEqual([
      "POST /v1/auth/pin/verify",
      "POST /v1/auth/refresh",
      "POST /v1/auth/pin/verify",
    ]);
  });
});

describe("refreshes queue across tabs under a Web Lock (D-067)", () => {
  it("takes the lock, and reads the CSRF cookie inside it", async () => {
    // While this tab waited, another one refreshed and replaced the cookie.
    const locks = fakeLocks(() => setCookie("csrf_local", "c2"));
    const heldDuringRefresh: boolean[] = [];
    const api_ = fakeApi({
      "POST /v1/auth/refresh": () => {
        heldDuringRefresh.push(locks.isHeld());
        return json(200, { access_token: "t" });
      },
    });
    try {
      await refreshAccessToken();
    } finally {
      locks.uninstall();
    }

    expect(locks.requested).toEqual([REFRESH_LOCK]);
    expect(heldDuringRefresh).toEqual([true]);
    expect(api_.calls[0]?.headers.get("X-CSRF")).toBe("c2");
  });
});

describe("what ends a session, and what doesn't", () => {
  it("the API's refusal of a refresh signs the tab out, with no second try", async () => {
    useSession.getState().signIn("old");
    const api_ = fakeApi({
      "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED"),
    });

    await expect(refreshAccessToken()).rejects.toBeInstanceOf(ApiError);
    expect(api_.sent()).toEqual(["POST /v1/auth/refresh"]);
    expect(useSession.getState().status).toBe("signed-out");
  });

  it("a network failure or a 5xx during a refresh leaves the session alone", async () => {
    useSession.getState().signIn("old");
    fakeApi({
      "POST /v1/auth/refresh": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    await expect(refreshAccessToken()).rejects.toThrow(TypeError);
    expect(useSession.getState().status).toBe("signed-in");

    fakeApi({ "POST /v1/auth/refresh": () => envelope(503, "NOT_READY") });
    await expect(refreshAccessToken()).rejects.toBeInstanceOf(ApiError);
    expect(useSession.getState().status).toBe("signed-in");
  });

  it("a wrong PIN is not the end of the session", async () => {
    useSession.getState().signIn("t");
    const api_ = fakeApi({
      "POST /v1/auth/pin/verify": () =>
        envelope(401, "PIN_INVALID", { attempts_left: 3 }),
    });

    await expect(
      api.post("/v1/auth/pin/verify", { body: { pin: "1111" } }),
    ).rejects.toMatchObject({ code: "PIN_INVALID" });
    expect(api_.sent()).toEqual(["POST /v1/auth/pin/verify"]);
    expect(useSession.getState().status).toBe("signed-in");
  });

  it.each([
    [401, "SESSION_REVOKED"],
    [401, "AUTH_REQUIRED"],
    [403, "ACCOUNT_BANNED"],
    [403, "ACCOUNT_FROZEN"],
  ])("%i %s signs the tab out", async (status, code) => {
    useSession.getState().signIn("t");
    fakeApi({ "GET /v1/me": () => envelope(status, code) });

    await expect(api.get("/v1/me")).rejects.toMatchObject({ code });
    expect(useSession.getState().status).toBe("signed-out");
  });

  it("a 403 that isn't about the account leaves the session alone", async () => {
    useSession.getState().signIn("t");
    fakeApi({ "GET /v1/me": () => envelope(403, "FORBIDDEN") });

    await expect(api.get("/v1/me")).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(useSession.getState().status).toBe("signed-in");
  });

  it("logout's own 401 isn't sent into a refresh", async () => {
    const api_ = fakeApi({
      "POST /v1/auth/logout": () => envelope(401, "TOKEN_EXPIRED"),
    });

    await expect(api.post("/v1/auth/logout")).rejects.toBeInstanceOf(ApiError);
    expect(api_.sent()).toEqual(["POST /v1/auth/logout"]);
  });
});
