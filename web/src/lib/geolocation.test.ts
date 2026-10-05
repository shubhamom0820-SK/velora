import { afterEach, describe, expect, it } from "vitest";

import {
  currentPosition,
  locationPermission,
  POSITION_MAX_AGE_MS,
  POSITION_TIMEOUT_MS,
  PositionError,
} from "./geolocation";
import {
  restoreGeolocation,
  stubPermission,
  stubPosition,
} from "./testing/fakeGeolocation";

afterEach(() => restoreGeolocation());

describe("the browser's position (T-4.10)", () => {
  it("is latitude and longitude, asked for without high accuracy, a 15 s wait, and a reading up to 5 minutes old", async () => {
    const ask = stubPosition({ lat: 31.2139, lng: 75.768 });

    await expect(currentPosition()).resolves.toEqual({
      lat: 31.2139,
      lng: 75.768,
    });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(ask.mock.calls[0]?.[2]).toEqual({
      enableHighAccuracy: false,
      timeout: 15_000,
      maximumAge: 300_000,
    });
    expect([POSITION_TIMEOUT_MS, POSITION_MAX_AGE_MS]).toEqual([
      15_000, 300_000,
    ]);
  });

  it.each([
    [1, "denied"],
    [2, "unavailable"],
    [3, "timeout"],
  ] as const)("a refusal with code %i is %s", async (code, reason) => {
    stubPosition({ code });

    const failure = await currentPosition().catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(PositionError);
    expect((failure as PositionError).reason).toBe(reason);
  });

  it("is unavailable in a browser without geolocation", async () => {
    restoreGeolocation();
    expect("geolocation" in navigator).toBe(false);

    const failure = await currentPosition().catch((error: unknown) => error);

    expect((failure as PositionError).reason).toBe("unavailable");
  });
});

describe("what the browser has decided (T-4.10)", () => {
  it.each(["granted", "denied", "prompt"] as const)(
    "is %s when it says so, asked about geolocation",
    async (state) => {
      const query = stubPermission(state);

      await expect(locationPermission()).resolves.toBe(state);
      expect(query).toHaveBeenCalledWith({ name: "geolocation" });
    },
  );

  it("is unknown without the Permissions API, or when the query fails", async () => {
    await expect(locationPermission()).resolves.toBe("unknown");

    stubPermission(new TypeError("not supported"));
    await expect(locationPermission()).resolves.toBe("unknown");
  });
});
