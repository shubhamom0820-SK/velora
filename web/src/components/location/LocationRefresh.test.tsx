import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/lib/queries/keys";
import type { Me } from "@/lib/queries/me";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
  type Route,
} from "@/lib/testing/fakeApi";
import {
  restoreGeolocation,
  stubPermission,
  stubPosition,
  type Answer,
} from "@/lib/testing/fakeGeolocation";
import { resetSession } from "@/store/session";

import { LocationRefresh } from "./LocationRefresh";

function me(location: Me["profile"]["location"]): Me {
  return { id: "u1", onboarding_step: "done", profile: { location } } as Me;
}

const PHAGWARA = { lat: 31.2224, lng: 75.7708 };

function setUp(
  location: Me["profile"]["location"],
  permission: PermissionState | null,
  answer: Answer = PHAGWARA,
  put: Route = () => json(200, me("fresh")),
) {
  if (permission) stubPermission(permission);
  const ask = stubPosition(answer);
  const api_ = fakeApi({ "PUT /v1/me/location": put });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const person = me(location);
  const view = render(
    <QueryClientProvider client={client}>
      <LocationRefresh me={person} />
    </QueryClientProvider>,
  );
  const rerender = () =>
    view.rerender(
      <QueryClientProvider client={client}>
        <LocationRefresh me={person} />
      </QueryClientProvider>,
    );
  return { ask, api_, client, rerender };
}

/** Long enough for the permission query and a reading to have happened. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 20));

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
});

afterEach(() => {
  restoreGeolocation();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

describe("refreshing a stale location when the app opens (T-4.10, D-220)", () => {
  it("sends a new reading, once, where the browser already allows it", async () => {
    const { api_, client, rerender } = setUp("stale", "granted");

    await waitFor(() => expect(api_.calls).toHaveLength(1));
    rerender();
    await settle();

    expect(api_.calls).toMatchObject([
      { method: "PUT", path: "/v1/me/location", body: PHAGWARA },
    ]);
    expect(client.getQueryData<Me>(queryKeys.me())?.profile.location).toBe(
      "fresh",
    );
  });

  it("leaves a fresh location alone", async () => {
    const { ask, api_ } = setUp("fresh", "granted");
    await settle();
    expect(ask).not.toHaveBeenCalled();
    expect(api_.calls).toHaveLength(0);
  });

  it.each([
    ["would ask", "prompt"],
    ["has said no", "denied"],
    ["can't say", null],
  ] as const)(
    "never asks: a browser that %s is left alone",
    async (_, permission) => {
      const { ask, api_ } = setUp("stale", permission);
      await settle();
      expect(ask).not.toHaveBeenCalled();
      expect(api_.calls).toHaveLength(0);
    },
  );

  it("keeps the old location, silently, when there's no reading", async () => {
    const { ask, api_ } = setUp("stale", "granted", { code: 2 });
    await waitFor(() => expect(ask).toHaveBeenCalled());
    await settle();
    expect(api_.calls).toHaveLength(0);
  });

  it("keeps the old location, silently, when the server refuses the new one", async () => {
    const { api_, client } = setUp("stale", "granted", PHAGWARA, () =>
      envelope(400, "VALIDATION_ERROR"),
    );
    await waitFor(() => expect(api_.calls).toHaveLength(1));
    await settle();
    expect(client.getQueryData(queryKeys.me())).toBeUndefined();
  });
});
