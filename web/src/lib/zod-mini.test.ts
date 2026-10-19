// @vitest-environment node
import { describe, expect, it } from "vitest";

// Only this module, never @/lib/zod: the setting is zod's core's, shared by
// both builds, so importing the other here would prove nothing about this one.
import { z } from "./zod-mini";

describe("zod/mini never compiles its parsers (T-9.10, T-3.11)", () => {
  it("is jitless, so it never probes new Function under the CSP", () => {
    expect(z.config().jitless).toBe(true);
  });

  it("parses as zod's full build did: unknown keys dropped, a float refused as int", () => {
    const schema = z.object({ balance: z.int() });
    expect(schema.safeParse({ balance: 5, extra: 1 })).toMatchObject({
      success: true,
      data: { balance: 5 },
    });
    expect(schema.safeParse({ balance: 5.5 }).success).toBe(false);
    expect(schema.safeParse({ balance: "5" }).success).toBe(false);
  });
});
