import { vi } from "vitest";

/**
 * A stand-in for the browser's position and its permission (T-4.10): what
 * `navigator.geolocation` answers, and what `navigator.permissions` says the
 * browser has decided. jsdom has neither. Test-only; nothing in the app
 * imports it. `restoreGeolocation()` takes both away again.
 */

export type Answer =
  | { lat: number; lng: number }
  | { code: 1 | 2 | 3 } // denied, unavailable, timeout
  | "never"; // the browser never answers

export function stubPosition(answer: Answer) {
  const getCurrentPosition = vi.fn(
    (
      resolve: PositionCallback,
      reject?: PositionErrorCallback | null,
      options?: PositionOptions,
    ) => {
      void options;
      if (answer === "never") return;
      if ("code" in answer) {
        reject?.({ code: answer.code } as GeolocationPositionError);
      } else {
        resolve({
          coords: { latitude: answer.lat, longitude: answer.lng },
        } as GeolocationPosition);
      }
    },
  );
  Object.defineProperty(navigator, "geolocation", {
    value: { getCurrentPosition },
    configurable: true,
  });
  return getCurrentPosition;
}

export function stubPermission(state: PermissionState | Error) {
  const query = vi.fn(async () => {
    if (state instanceof Error) throw state;
    return { state };
  });
  Object.defineProperty(navigator, "permissions", {
    value: { query },
    configurable: true,
  });
  return query;
}

export function restoreGeolocation() {
  for (const key of ["geolocation", "permissions"]) {
    if (Object.prototype.hasOwnProperty.call(navigator, key)) {
      Reflect.deleteProperty(navigator, key);
    }
  }
}
