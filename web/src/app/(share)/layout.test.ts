import { describe, expect, it } from "vitest";

import { dynamic, metadata } from "./layout";

describe("/@username's layout (T-6.8, D-544)", () => {
  it("is never indexed, in any environment", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });

  it("renders per request: for the nonce, and so a link turned off shows nothing at once", () => {
    expect(dynamic).toBe("force-dynamic");
  });
});
