import { describe, expect, it } from "vitest";

import { dayLabel, duration, knottedAgo } from "./format";

const at = (y: number, m: number, d: number, h = 12) =>
  new Date(y, m - 1, d, h).getTime();

describe("the conversation's times", () => {
  it("names today and yesterday, by the reader's own days", () => {
    const now = at(2026, 10, 9, 0.5);

    expect(dayLabel(new Date(at(2026, 10, 9, 0.1)).toISOString(), now)).toBe(
      "Today",
    );
    expect(dayLabel(new Date(at(2026, 10, 8, 23.9)).toISOString(), now)).toBe(
      "Yesterday",
    );
    expect(dayLabel(new Date(at(2026, 10, 6)).toISOString(), now)).toMatch(
      /6 Oct/,
    );
  });

  it("says how long ago a Knot was tied", () => {
    const now = at(2026, 10, 9);

    expect(knottedAgo(new Date(at(2026, 10, 9, 1)).toISOString(), now)).toBe(
      "Knotted today",
    );
    expect(knottedAgo(new Date(at(2026, 10, 8)).toISOString(), now)).toBe(
      "Knotted yesterday",
    );
    expect(knottedAgo(new Date(at(2026, 10, 6)).toISOString(), now)).toBe(
      "Knotted 3 days ago",
    );
  });

  it("writes a voice note's length as minutes and seconds", () => {
    expect(duration(0)).toBe("0:00");
    expect(duration(12)).toBe("0:12");
    expect(duration(60)).toBe("1:00");
  });
});
