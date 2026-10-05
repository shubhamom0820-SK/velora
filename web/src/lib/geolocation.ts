/**
 * The browser's position (T-4.10, D-034). Asked for only when the person taps
 * to share it on the location question, or, when the app opens, if the browser
 * already allows it: never a prompt they didn't ask for (D-220).
 *
 * The page may ask at all only because the Permissions-Policy says
 * `geolocation=(self)` (security-headers.ts); under `geolocation=()` the
 * browser refuses without asking, as `denied`.
 */

export type Position = { lat: number; lng: number };

/** Why there's no position: each sends the person to the area picker. */
export type PositionFailure = "denied" | "unavailable" | "timeout";

export class PositionError extends Error {
  constructor(readonly reason: PositionFailure) {
    super(`No position: ${reason}`);
    this.name = "PositionError";
  }
}

/** How long to wait for a reading before offering the picker instead. */
export const POSITION_TIMEOUT_MS = 15_000;

/** A reading the browser already has, this recent, will do. */
export const POSITION_MAX_AGE_MS = 5 * 60_000;

// GeolocationPositionError's codes, by value: the constants live on the error
// object, which a browser's own errors carry but a plain object needn't.
const PERMISSION_DENIED = 1;
const TIMEOUT = 3;

/** The position, or a `PositionError` saying why not. */
export function currentPosition(): Promise<Position> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return Promise.reject(new PositionError("unavailable"));
  }
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve({ lat: coords.latitude, lng: coords.longitude }),
      (error) =>
        reject(
          new PositionError(
            error.code === PERMISSION_DENIED
              ? "denied"
              : error.code === TIMEOUT
                ? "timeout"
                : "unavailable",
          ),
        ),
      {
        enableHighAccuracy: false,
        timeout: POSITION_TIMEOUT_MS,
        maximumAge: POSITION_MAX_AGE_MS,
      },
    );
  });
}

/** What the browser has already decided, or `unknown` where it can't say. */
export type LocationPermission = PermissionState | "unknown";

/** Asks the browser what it has decided, never the person. */
export async function locationPermission(): Promise<LocationPermission> {
  try {
    if (typeof navigator === "undefined" || !navigator.permissions) {
      return "unknown";
    }
    const status = await navigator.permissions.query({ name: "geolocation" });
    return status.state;
  } catch {
    return "unknown";
  }
}
