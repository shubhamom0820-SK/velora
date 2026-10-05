import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
} from "@/lib/testing/fakeGeolocation";
import { resetSession } from "@/store/session";

import { LocationStep } from "./LocationStep";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/onboarding/location",
}));

function me(
  location: Me["profile"]["location"] = "none",
  onboarding_step: Me["onboarding_step"] = "username",
): Me {
  return { id: "u1", onboarding_step, profile: { location } } as Me;
}

const AREAS = [
  { id: "a1", city: "Phagwara", name: "Banga Road" },
  { id: "a2", city: "Phagwara", name: "Model Town" },
];

/** The API: the areas, and a location write answering `Me` as it now is. */
function api(put: Route = () => json(200, me("fresh"))) {
  return fakeApi({
    "GET /v1/areas": () => json(200, AREAS),
    "PUT /v1/me/location": put,
  });
}

function renderStep(person: Me = me()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <LocationStep me={person} />
    </QueryClientProvider>,
  );
}

const share = () =>
  userEvent.click(screen.getByRole("button", { name: "Share my location" }));

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
  nav.push.mockReset();
});

afterEach(() => {
  restoreGeolocation();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

describe("the location question (T-4.10, D-220)", () => {
  it("says why before asking, and asks the browser only when tapped", async () => {
    stubPermission("prompt");
    const ask = stubPosition({ lat: 31.2139, lng: 75.768 });
    api();

    renderStep();

    expect(
      screen.getByRole("heading", { name: "Where are you?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "We use your location to show you people nearby. Other people see only a distance, rounded to the kilometre.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAccessibleName(
      "Step 7 of 13",
    );
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/name",
    );
    await waitFor(() => expect(navigator.permissions.query).toHaveBeenCalled());
    expect(ask).not.toHaveBeenCalled();
  });

  it("sends the shared position and goes on to where the person now is", async () => {
    stubPosition({ lat: 31.2139, lng: 75.768 });
    const api_ = api();
    renderStep();

    await share();

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/username"),
    );
    expect(api_.calls.filter((c) => c.method === "PUT")).toMatchObject([
      { path: "/v1/me/location", body: { lat: 31.2139, lng: 75.768 } },
    ]);
  });

  it.each([
    [
      1,
      "Location is off for Velora in this browser, so pick your area instead.",
    ],
    [2, "We couldn't find your location, so pick your area instead."],
    [3, "Finding your location took too long, so pick your area instead."],
  ] as const)(
    "a browser answering %i lands on the area picker, saying why",
    async (code, why) => {
      stubPosition({ code });
      const api_ = api();
      renderStep();

      await share();

      expect(
        await screen.findByRole("heading", { name: "Pick your area" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("status")).toHaveTextContent(why);
      expect(
        await screen.findByRole("radio", { name: "Model Town" }),
      ).toBeInTheDocument();
      expect(api_.calls.some((c) => c.method === "PUT")).toBe(false);
    },
  );

  it("a position the server refuses, outside India, lands on the picker too", async () => {
    stubPosition({ lat: 51.5072, lng: -0.1276 });
    api(() =>
      envelope(400, "VALIDATION_ERROR", {
        fields: [{ field: "lat", problem: "must be inside India" }],
      }),
    );
    renderStep();

    await share();

    expect(await screen.findByRole("status")).toHaveTextContent(
      "That location is outside India, so pick your area instead.",
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("sends a picked area and goes on", async () => {
    const api_ = api();
    renderStep();

    await userEvent.click(
      screen.getByRole("button", { name: "Pick my area instead" }),
    );
    const continueButton = screen.getByRole("button", { name: "Continue" });
    expect(continueButton).toBeDisabled();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Model Town" }),
    );
    await userEvent.click(continueButton);

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/username"),
    );
    expect(api_.calls.filter((c) => c.method === "PUT")).toMatchObject([
      { body: { area_id: "a2" } },
    ]);
  });

  it("goes straight to the picker where the browser has already said no, offering no position", async () => {
    stubPermission("denied");
    const ask = stubPosition({ lat: 31.2139, lng: 75.768 });
    api();

    renderStep();

    expect(
      await screen.findByRole("heading", { name: "Pick your area" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Location is off for Velora in this browser",
    );
    expect(
      screen.queryByRole("button", { name: "Use my location instead" }),
    ).toBeNull();
    expect(ask).not.toHaveBeenCalled();
  });

  it("can go back from the picker to sharing, when the browser may still allow it", async () => {
    stubPosition({ code: 3 });
    api();
    renderStep();
    await share();

    await userEvent.click(
      await screen.findByRole("button", { name: "Use my location instead" }),
    );

    expect(
      screen.getByRole("heading", { name: "Where are you?" }),
    ).toBeInTheDocument();
  });

  it("says when the areas can't load, and tries again", async () => {
    let fail = true;
    fakeApi({
      "GET /v1/areas": () =>
        fail ? envelope(500, "INTERNAL") : json(200, AREAS),
    });
    renderStep();
    await userEvent.click(
      screen.getByRole("button", { name: "Pick my area instead" }),
    );

    expect(
      await screen.findByText("We couldn't load the areas."),
    ).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("radio", { name: "Banga Road" }),
    ).toBeInTheDocument();
  });

  it("says when there are no areas", async () => {
    fakeApi({ "GET /v1/areas": () => json(200, []) });
    renderStep();
    await userEvent.click(
      screen.getByRole("button", { name: "Pick my area instead" }),
    );

    expect(
      await screen.findByText("There are no areas to pick from yet."),
    ).toBeInTheDocument();
  });

  it("shows any other refusal where it is, without leaving", async () => {
    stubPosition({ lat: 31.2139, lng: 75.768 });
    api(() => envelope(429, "RATE_LIMITED", { retry_after_s: 60 }));
    renderStep();

    await share();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many tries. Wait a moment, then try again.",
    );
    expect(
      screen.getByRole("heading", { name: "Where are you?" }),
    ).toBeInTheDocument();
    expect(nav.push).not.toHaveBeenCalled();
  });

  it("opened again once set, says so and can keep it", async () => {
    api();
    renderStep(me("fresh", "about"));

    expect(
      screen.getByText(
        "Your location is set. Share it again, or pick your area, to change it.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Keep it as it is" }),
    );

    expect(nav.push).toHaveBeenCalledWith("/onboarding/about");
  });

  it("offers no 'keep' before a location is set", () => {
    api();
    renderStep();
    expect(
      screen.queryByRole("button", { name: "Keep it as it is" }),
    ).toBeNull();
  });
});
