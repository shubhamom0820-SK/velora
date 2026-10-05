import { describe, expect, it } from "vitest";

import { creditsCount, creditsText, creditsUnit, deltaText } from "./credits";

describe("Velas in words (D-049)", () => {
  it.each([
    [0, "0 Velas"],
    [1, "1 Vela"],
    [2, "2 Velas"],
    [1250, "1,250 Velas"],
    [125000, "1,25,000 Velas"],
  ])("says %i as %s", (count, words) => {
    expect(creditsText(count)).toBe(words);
  });

  it("names the unit alone, one or many", () => {
    expect(creditsUnit(1)).toBe("Vela");
    expect(creditsUnit(0)).toBe("Velas");
    expect(creditsUnit(30)).toBe("Velas");
  });

  it("groups a bare count the Indian way", () => {
    expect(creditsCount(450)).toBe("450");
    expect(creditsCount(100000)).toBe("1,00,000");
  });

  it.each([
    [30, "+30"],
    [-5, "−5"],
    [-1250, "−1,250"],
  ])("signs a change of %i as %s, with a real minus", (delta, text) => {
    expect(deltaText(delta)).toBe(text);
  });
});
