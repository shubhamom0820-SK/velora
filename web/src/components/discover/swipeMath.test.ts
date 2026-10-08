import { describe, expect, it } from "vitest";

import {
  FLING_DISTANCE,
  MAX_TILT,
  exitOf,
  stampsOf,
  swipeOf,
  tiltOf,
  type Release,
} from "./swipeMath";

const still = (mx: number, my: number): Release => ({
  movement: [mx, my],
  velocity: [0, 0],
  direction: [Math.sign(mx), Math.sign(my)],
});

const flick = (mx: number, my: number, v: number): Release => ({
  movement: [mx, my],
  velocity: [
    Math.abs(mx) > Math.abs(my) ? v : 0,
    Math.abs(my) >= Math.abs(mx) ? v : 0,
  ],
  direction: [Math.sign(mx), Math.sign(my)],
});

describe("swipeOf: a release becomes a swipe (T-6.5)", () => {
  it.each<[string, Release, string | null]>([
    ["right past 100 px", still(FLING_DISTANCE, 0), "like"],
    ["left past 100 px", still(-FLING_DISTANCE, 10), "pass"],
    ["up past 100 px", still(20, -FLING_DISTANCE), "super"],
    ["99 px right, slowly", still(FLING_DISTANCE - 1, 0), null],
    ["99 px up, slowly", still(0, -(FLING_DISTANCE - 1)), null],
    ["down, however far", still(0, 300), null],
    ["a fast flick right", flick(40, 0, 0.8), "like"],
    ["a fast flick left", flick(-40, 0, 0.8), "pass"],
    ["a fast flick up", flick(0, -40, 0.8), "super"],
    ["a flick too slow", flick(60, 0, 0.3), null],
    ["a fast twitch too short to be a flick", flick(10, 0, 2), null],
  ])("%s", (_, release, expected) => {
    expect(swipeOf(release)).toBe(expected);
  });

  it("calls a diagonal drag by its larger part: more up than sideways is a Super Like", () => {
    expect(swipeOf(still(110, -120))).toBe("super");
    expect(swipeOf(still(130, -120))).toBe("like");
  });
});

describe("tiltOf", () => {
  it("tilts with the drag, never past the limit", () => {
    expect(tiltOf(40, false)).toBe(2);
    expect(tiltOf(-40, false)).toBe(-2);
    expect(tiltOf(10_000, false)).toBe(MAX_TILT);
    expect(tiltOf(-10_000, false)).toBe(-MAX_TILT);
  });

  it("never tilts under reduced motion (08-DESIGN §3)", () => {
    expect(tiltOf(300, true)).toBe(0);
  });
});

describe("stampsOf: the LIKE, PASS and SUPER stamps, by drag distance", () => {
  it("grows one stamp with the drag, full at the fling distance", () => {
    expect(stampsOf(50, 0)).toEqual({ like: 0.5, pass: 0, super: 0 });
    expect(stampsOf(-200, 0)).toEqual({ like: 0, pass: 1, super: 0 });
    expect(stampsOf(0, -FLING_DISTANCE)).toEqual({
      like: 0,
      pass: 0,
      super: 1,
    });
    expect(stampsOf(0, 0)).toEqual({ like: 0, pass: 0, super: 0 });
  });
});

describe("exitOf", () => {
  it("sends a like right, a pass left and a Super Like up, off the screen", () => {
    expect(exitOf("like", 400, 800)[0]).toBeGreaterThan(400);
    expect(exitOf("pass", 400, 800)[0]).toBeLessThan(-400);
    expect(exitOf("super", 400, 800)[1]).toBeLessThan(-800);
  });
});
