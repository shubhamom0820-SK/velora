import { describe, expect, it } from "vitest";

import { en } from "./en";
import { t, type MessageKey } from "./t";

describe("t", () => {
  it("returns the string for a key", () => {
    expect(t("ui.close")).toBe(en.ui.close);
  });

  it("fills placeholders from values", () => {
    expect(t("ui.counter", { count: 12, max: 300 })).toBe("12/300");
  });

  it("leaves a placeholder with no value visible", () => {
    expect(t("ui.counter", { count: 12 })).toBe("12/{max}");
  });

  it("throws for a key that doesn't end at a string", () => {
    // Typed code can't name these (t.type-test.ts); the casts reach the runtime guard.
    expect(() => t("ui" as MessageKey)).toThrow('No string for "ui"');
    expect(() => t("ui.nope" as MessageKey)).toThrow('No string for "ui.nope"');
  });
});
