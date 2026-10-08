import type { SwipeDirection } from "@/lib/queries/discover";

/**
 * How a drag on the top card becomes a swipe (T-6.5). No React, no DOM: the
 * deck feeds it what @use-gesture/react measured and draws what it returns.
 */

/** A release this far from where it started swipes (px). */
export const FLING_DISTANCE = 100;
/** Or a release this fast, in @use-gesture's px per ms. */
export const FLING_VELOCITY = 0.5;
/** A fast flick still has to move this far, so a tap never swipes (px). */
export const FLICK_MIN_DISTANCE = 24;
/** The most a card tilts as it is dragged (degrees). */
export const MAX_TILT = 15;
/** How far a drag tilts it: 1° per this many px. */
const PX_PER_DEGREE = 20;

export type Release = {
  /** Movement since the press: [x, y], y down. */
  movement: readonly [number, number];
  /** Speed at release, each axis's magnitude (px/ms). */
  velocity: readonly [number, number];
  /** Direction at release, each axis -1, 0 or 1. */
  direction: readonly [number, number];
};

/**
 * Which swipe a release makes, or null to spring back. Up is a Super Like,
 * right a like, left a pass: by distance past `FLING_DISTANCE`, or by a flick
 * past `FLING_VELOCITY` that moved at least `FLICK_MIN_DISTANCE`. Up wins
 * only when the drag went more up than sideways.
 */
export function swipeOf({
  movement: [mx, my],
  velocity: [vx, vy],
  direction: [dx, dy],
}: Release): SwipeDirection | null {
  const upward = -my > Math.abs(mx);
  if (upward && -my >= FLING_DISTANCE) return "super";
  if (!upward && Math.abs(mx) >= FLING_DISTANCE)
    return mx > 0 ? "like" : "pass";
  if (upward && vy >= FLING_VELOCITY && dy < 0 && -my >= FLICK_MIN_DISTANCE) {
    return "super";
  }
  if (
    !upward &&
    vx >= FLING_VELOCITY &&
    dx !== 0 &&
    Math.abs(mx) >= FLICK_MIN_DISTANCE
  ) {
    return dx > 0 ? "like" : "pass";
  }
  return null;
}

/** The card's tilt for a drag of `x` px: none under reduced motion (08-DESIGN §3). */
export function tiltOf(x: number, reducedMotion: boolean): number {
  if (reducedMotion) return 0;
  return Math.max(-MAX_TILT, Math.min(MAX_TILT, x / PX_PER_DEGREE));
}

/** How strongly each stamp shows, 0 to 1, for a drag of [x, y]. */
export function stampsOf(x: number, y: number) {
  const part = (distance: number) =>
    Math.max(0, Math.min(1, distance / FLING_DISTANCE));
  const upward = -y > Math.abs(x);
  return {
    like: upward ? 0 : part(x),
    pass: upward ? 0 : part(-x),
    super: upward ? part(-y) : 0,
  };
}

/** Where a swiped card flies to, off the screen: [x, y] px. */
export function exitOf(
  direction: SwipeDirection,
  width: number,
  height: number,
): readonly [number, number] {
  if (direction === "super") return [0, -height * 1.5];
  return [(direction === "like" ? 1 : -1) * width * 1.5, 0];
}
