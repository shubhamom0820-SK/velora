import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";

import { shouldRetry } from "./QueryProvider";

function apiError(status: number) {
  return new ApiError({ code: "X", message: "x", status });
}

describe("shouldRetry", () => {
  it.each([400, 401, 402, 404, 409, 422, 429])(
    "never retries a %i: it is the API's answer",
    (status) => {
      expect(shouldRetry(0, apiError(status))).toBe(false);
    },
  );

  it.each([
    ["a 500", apiError(500)],
    ["a 503", apiError(503)],
    ["a network failure", new TypeError("Failed to fetch")],
  ])("retries %s twice, then stops", (_, error) => {
    expect(shouldRetry(0, error)).toBe(true);
    expect(shouldRetry(1, error)).toBe(true);
    expect(shouldRetry(2, error)).toBe(false);
  });
});
