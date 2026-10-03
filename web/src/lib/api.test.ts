import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetSession, useSession } from "@/store/session";

import { api, apiBaseUrl, ApiError } from "./api";

const fetchMock = vi.fn<typeof fetch>();

function reply(
  status: number,
  body?: unknown,
  contentType = "application/json",
) {
  return new Response(
    body === undefined
      ? null
      : typeof body === "string"
        ? body
        : JSON.stringify(body),
    { status, headers: { "Content-Type": contentType } },
  );
}

/** The request `fetch` was called with, as the wrapper built it. */
function sent() {
  const [url, init] = fetchMock.mock.calls[0] ?? [];
  return { url: String(url), init: init ?? {} };
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(
    () => {
      throw new Error("expected the call to fail");
    },
    (e: unknown) => e,
  );
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test/");
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    resetSession();
  });

  it("GETs base URL + path and returns the parsed JSON", async () => {
    fetchMock.mockResolvedValue(reply(200, { status: "ok" }));

    const health = await api.get("/healthz");

    expect(health).toEqual({ status: "ok" });
    expect(sent().url).toBe("https://api.test/healthz");
    expect(sent().init.method).toBe("GET");
  });

  it("sends the access token only when there is one", async () => {
    fetchMock.mockImplementation(async () => reply(200, { status: "ok" }));

    await api.get("/healthz");
    expect(new Headers(sent().init.headers).has("Authorization")).toBe(false);

    useSession.getState().signIn("jwt-123");
    fetchMock.mockClear();
    await api.get("/healthz");
    expect(new Headers(sent().init.headers).get("Authorization")).toBe(
      "Bearer jwt-123",
    );
  });

  it("sends a body as JSON with its content type", async () => {
    fetchMock.mockResolvedValue(reply(204));
    // No POST route exists yet (T-3 adds them), so this reaches past the types.
    const post = api.post as unknown as (
      path: string,
      options: { body: unknown },
    ) => Promise<unknown>;

    const result = await post("/v1/me/dob", { body: { dob: "2000-01-31" } });

    expect(result).toBeUndefined();
    expect(sent().init.method).toBe("POST");
    expect(sent().init.body).toBe('{"dob":"2000-01-31"}');
    expect(new Headers(sent().init.headers).get("Content-Type")).toBe(
      "application/json",
    );
  });

  it.each([
    [
      400,
      "VALIDATION_ERROR",
      { fields: [{ field: "dob", problem: "Field required" }] },
    ],
    [401, "AUTH_REQUIRED", undefined],
    [402, "INSUFFICIENT_CREDITS", { required: 5, balance: 2 }],
    [503, "NOT_READY", { database: "ok", redis: "fail" }],
  ])(
    "turns a %i error envelope into ApiError %s",
    async (status, code, details) => {
      fetchMock.mockResolvedValue(
        reply(status, {
          error: {
            code,
            message: "Server says why.",
            ...(details && { details }),
          },
        }),
      );

      const error = await failure(api.get("/healthz"));

      expect(error).toMatchObject({
        code,
        status,
        message: "Server says why.",
      });
      expect(error.details).toEqual(details);
    },
  );

  it("reports a response that isn't our envelope as INTERNAL, with its status", async () => {
    fetchMock.mockResolvedValue(
      reply(502, "<html>Bad gateway</html>", "text/html"),
    );

    const error = await failure(api.get("/healthz"));

    expect(error).toMatchObject({ code: "INTERNAL", status: 502 });
  });

  it("lets a network failure through as it is", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.get("/healthz")).rejects.toThrow(TypeError);
  });

  it("needs NEXT_PUBLIC_API_URL outside next dev", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");

    expect(() => apiBaseUrl()).toThrow("NEXT_PUBLIC_API_URL is not set.");
  });

  it("falls back to the local API under next dev", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "development");

    expect(apiBaseUrl()).toBe("http://127.0.0.1:8000");
  });
});
