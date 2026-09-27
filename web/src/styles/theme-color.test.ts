// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { THEME_COLOR } from "./theme-color";

// P-28: `<meta name="theme-color">` can't read a CSS variable, so theme-color.ts
// copies `--chrome`. This fails the day the copy and tokens.css drift apart.
describe("THEME_COLOR", () => {
  it("equals --chrome in tokens.css", () => {
    const tokens = readFileSync(
      new URL("./tokens.css", import.meta.url),
      "utf8",
    );
    const chrome = /--chrome:\s*([^;]+);/.exec(tokens)?.[1]?.trim();

    expect(chrome).toBeDefined();
    expect(THEME_COLOR.toLowerCase()).toBe(chrome?.toLowerCase());
  });
});
