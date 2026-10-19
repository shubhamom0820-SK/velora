import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
import { resetSession, useSession } from "@/store/session";

import { filtersOf } from "@/components/discover/filterParams";
import { HOME_FEED, useDiscover } from "@/lib/queries/discover";

import { AppGate } from "./AppGate";
import { OnboardingGate } from "./OnboardingGate";
import { RELOCK_AFTER_HIDDEN_MS } from "./PinLock";
import { SessionRestorer } from "./SessionRestorer";
import { SignedInRedirect } from "./SignedInRedirect";

const nav = vi.hoisted(() => ({ replace: vi.fn(), pathname: "/" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => nav.pathname,
}));

function me(onboarding_step: string, has_pin = false, location = "fresh") {
  return { id: "u1", onboarding_step, has_pin, profile: { location } };
}

const restored: Route = () => json(200, { access_token: "t" });

function renderGate(gate: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SessionRestorer />
      {gate}
    </QueryClientProvider>,
  );
}

const Secret = () => <p>Behind the gate</p>;

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
  nav.replace.mockReset();
  nav.pathname = "/";
});

afterEach(() => {
  restoreGeolocation();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

describe("the app's gate (T-3.10)", () => {
  it("sends someone with no session to /login, showing nothing behind it", async () => {
    fakeApi({ "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED") });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Behind the gate")).not.toBeInTheDocument();
  });

  it("lets a finished onboarding in", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("refreshes a stale location on the way in, where the browser allows (T-4.10)", async () => {
    stubPermission("granted");
    stubPosition({ lat: 31.2224, lng: 75.7708 });
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done", false, "stale")),
      "PUT /v1/me/location": () => json(200, me("done")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    await waitFor(() =>
      expect(api_.calls.filter((c) => c.method === "PUT")).toMatchObject([
        { path: "/v1/me/location", body: { lat: 31.2224, lng: 75.7708 } },
      ]),
    );
  });

  it("sends someone past Name without a location to the location question (D-220)", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("photos", false, "none")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/location"),
    );
  });

  it("sends an unfinished onboarding to its step's URL", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("seeking")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/looking-for"),
    );
    expect(screen.queryByText("Behind the gate")).not.toBeInTheDocument();
  });

  it("offers a retry, not /login, when the restore had no signal", async () => {
    fakeApi({
      "POST /v1/auth/refresh": () =>
        Promise.reject(new TypeError("Failed to fetch")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't reach Velora",
    );
    expect(nav.replace).not.toHaveBeenCalled();

    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
    });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
  });

  it("offers a retry when /me fails with a 5xx", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => envelope(503, "NOT_READY"),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });
});

describe("the deck's first page, started alongside /me (T-9.10, D-1033)", () => {
  const page = { items: [], next_cursor: null, swipes_left: 50 };

  /** A child of the gate reading the deck's query, as DiscoverScreen does. */
  function DeckProbe() {
    const feed = useDiscover(
      HOME_FEED,
      filtersOf(new URLSearchParams(window.location.search)),
    );
    return <p>{feed.isSuccess ? "Feed read" : "Feed waiting"}</p>;
  }

  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("asks for the feed before /me has answered, on /discover", async () => {
    nav.pathname = "/discover";
    let answerMe: (response: Response) => void = () => {};
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => new Promise((done) => (answerMe = done)),
      "GET /v1/discover": () => json(200, page),
    });

    renderGate(
      <AppGate>
        <DeckProbe />
      </AppGate>,
    );

    await waitFor(() => expect(api_.sent()).toContain("GET /v1/discover"));
    expect(screen.queryByText(/Feed/)).not.toBeInTheDocument();
    act(() => answerMe(json(200, me("done"))));

    // The deck reads the page already asked for: one request, never two.
    expect(await screen.findByText("Feed read")).toBeInTheDocument();
    expect(api_.sent().filter((sent) => sent === "GET /v1/discover")).toEqual([
      "GET /v1/discover",
    ]);
  });

  it("sends it with the access token, never before there is one", async () => {
    nav.pathname = "/discover";
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
      "GET /v1/discover": () => json(200, page),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    await waitFor(() => expect(api_.sent()).toContain("GET /v1/discover"));
    const sent = api_.sent();
    expect(sent.indexOf("POST /v1/auth/refresh")).toBeLessThan(
      sent.indexOf("GET /v1/discover"),
    );
    const feed = api_.calls.find((call) => call.path === "/v1/discover");
    expect(feed?.headers.get("Authorization")).toBe("Bearer t");
  });

  it("asks with the filters in the address, the deck's own key", async () => {
    nav.pathname = "/discover";
    window.history.replaceState(null, "", "/discover?verified=true");
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
      "GET /v1/discover": () => json(200, page),
    });

    renderGate(
      <AppGate>
        <DeckProbe />
      </AppGate>,
    );

    expect(await screen.findByText("Feed read")).toBeInTheDocument();
    const feeds = api_.calls.filter((call) => call.path === "/v1/discover");
    expect(feeds).toHaveLength(1);
    expect(feeds[0]?.query.get("verified")).toBe("true");
  });

  it("asks for no feed anywhere but /discover", async () => {
    nav.pathname = "/chats";
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    expect(api_.sent()).not.toContain("GET /v1/discover");
  });

  it("asks for no feed when there is no session", async () => {
    nav.pathname = "/discover";
    const api_ = fakeApi({
      "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED"),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(api_.sent()).toEqual(["POST /v1/auth/refresh"]);
  });

  it("shows nothing of a feed refused to an unfinished onboarding, and goes to its step", async () => {
    nav.pathname = "/discover";
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("seeking")),
      "GET /v1/discover": () =>
        envelope(403, "ONBOARDING_INCOMPLETE", { step: "seeking" }),
    });

    renderGate(
      <AppGate>
        <DeckProbe />
      </AppGate>,
    );

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/looking-for"),
    );
    expect(api_.sent()).toContain("GET /v1/discover");
    expect(screen.queryByText(/Feed/)).not.toBeInTheDocument();
  });

  it("shows nothing of a feed refused to a frozen account, which is signed out as before", async () => {
    nav.pathname = "/discover";
    const api_ = fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => envelope(403, "ACCOUNT_FROZEN"),
      "GET /v1/discover": () => envelope(403, "ACCOUNT_FROZEN"),
    });

    renderGate(
      <AppGate>
        <DeckProbe />
      </AppGate>,
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(api_.sent()).toContain("GET /v1/discover");
    expect(screen.queryByText(/Feed/)).not.toBeInTheDocument();
  });
});

describe("Me stays fresh after a write puts it in the cache", () => {
  it("opens a screen without asking /me again", async () => {
    const api_ = fakeApi({});
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    client.setQueryData(["me"], me("done"));
    useSession.getState().signIn("t", { fresh: true });

    render(
      <QueryClientProvider client={client}>
        <AppGate>
          <Secret />
        </AppGate>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    expect(api_.calls).toHaveLength(0);
  });
});

describe("onboarding's gate (T-3.10, D-080)", () => {
  it("sends a step ahead of the person's back to theirs", async () => {
    nav.pathname = "/onboarding/name";
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("seeking")),
    });

    renderGate(
      <OnboardingGate>
        <Secret />
      </OnboardingGate>,
    );

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/looking-for"),
    );
    expect(screen.queryByText("Behind the gate")).not.toBeInTheDocument();
  });

  it.each(["/onboarding/looking-for", "/onboarding/birthday"])(
    "opens %s at or before the person's step, as an edit (D-068)",
    async (path) => {
      nav.pathname = path;
      fakeApi({
        "POST /v1/auth/refresh": restored,
        "GET /v1/me": () => json(200, me("seeking")),
      });

      renderGate(
        <OnboardingGate>
          <Secret />
        </OnboardingGate>,
      );

      expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
      expect(nav.replace).not.toHaveBeenCalled();
    },
  );

  it("sends a later screen back to the location question while none is set (D-220)", async () => {
    nav.pathname = "/onboarding/username";
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("about", false, "none")),
    });

    renderGate(
      <OnboardingGate>
        <Secret />
      </OnboardingGate>,
    );

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/location"),
    );
    expect(screen.queryByText("Behind the gate")).not.toBeInTheDocument();
  });

  it("opens the location question past Name, as an edit once one is set", async () => {
    nav.pathname = "/onboarding/location";
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("about")),
    });

    renderGate(
      <OnboardingGate>
        <Secret />
      </OnboardingGate>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("keeps the location question for after Name", async () => {
    nav.pathname = "/onboarding/location";
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("profile", false, "none")),
    });

    renderGate(
      <OnboardingGate>
        <Secret />
      </OnboardingGate>,
    );

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/name"),
    );
  });

  it("sends a finished onboarding to the app", async () => {
    nav.pathname = "/onboarding/birthday";
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
    });

    renderGate(
      <OnboardingGate>
        <Secret />
      </OnboardingGate>,
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/discover"));
  });

  it("sends someone with no session to /login", async () => {
    nav.pathname = "/onboarding/birthday";
    fakeApi({ "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED") });

    renderGate(
      <OnboardingGate>
        <Secret />
      </OnboardingGate>,
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
  });
});

describe("/login with a session already (T-3.10)", () => {
  it("moves on to the location question when that's where the person is (D-220)", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("username", false, "none")),
    });

    renderGate(<SignedInRedirect />);

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/location"),
    );
  });

  it("moves on to the person's step", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("dob")),
    });

    renderGate(<SignedInRedirect />);

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/birthday"),
    );
  });

  it("stays when there's none", async () => {
    const api_ = fakeApi({
      "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED"),
    });

    renderGate(<SignedInRedirect />);

    await waitFor(() =>
      expect(useSession.getState().status).toBe("signed-out"),
    );
    expect(api_.sent()).toEqual(["POST /v1/auth/refresh"]);
    expect(nav.replace).not.toHaveBeenCalled();
  });
});

describe("the PIN lock (T-3.10, D-069)", () => {
  function lockedApp(pinVerify: Route) {
    return fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done", true)),
      "POST /v1/auth/pin/verify": pinVerify,
      "POST /v1/auth/logout": () => json(204),
    });
  }

  async function enter(pin: string) {
    for (const digit of pin) {
      await userEvent.click(screen.getByRole("button", { name: digit }));
    }
  }

  it("is up on load with a PIN, and the app behind it is inert", async () => {
    lockedApp(() => json(204));

    const { container } = renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByRole("dialog")).toHaveAccessibleName(
      "Enter your PIN",
    );
    expect(container.querySelector("[inert]")).toHaveTextContent(
      "Behind the gate",
    );
  });

  it("opens with the right PIN", async () => {
    const api_ = lockedApp(() => json(204));
    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );
    await screen.findByRole("dialog");

    await enter("4829");

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(
      api_.calls.find((c) => c.path === "/v1/auth/pin/verify")?.body,
    ).toEqual({
      pin: "4829",
    });
    expect(document.querySelector("[inert]")).toBeNull();
  });

  it("isn't there without a PIN", async () => {
    fakeApi({
      "POST /v1/auth/refresh": restored,
      "GET /v1/me": () => json(200, me("done")),
    });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("isn't put up after a fresh sign-in, which just proved the number", async () => {
    fakeApi({ "GET /v1/me": () => json(200, me("done", true)) });
    useSession.getState().signIn("t", { fresh: true });

    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );

    expect(await screen.findByText("Behind the gate")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it.each([
    [3, "Wrong PIN. 3 tries left."],
    [1, "Wrong PIN. 1 try left."],
  ])("says how many tries are left (%i)", async (left, message) => {
    lockedApp(() => envelope(401, "PIN_INVALID", { attempts_left: left }));
    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );
    await screen.findByRole("dialog");

    await enter("1111");

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("offers only the way out when the PIN can't be checked", async () => {
    lockedApp(() => envelope(401, "PIN_INVALID", { reset_required: true }));
    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );
    await screen.findByRole("dialog");

    await enter("4829");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your PIN can't be checked.",
    );
    expect(screen.getByRole("button", { name: "1" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Forgot your PIN? Sign out" }),
    ).toBeEnabled();
  });

  it("goes to /login at the fifth wrong PIN, SESSION_REVOKED", async () => {
    lockedApp(() => envelope(401, "SESSION_REVOKED"));
    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );
    await screen.findByRole("dialog");

    await enter("1111");

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(useSession.getState().accessToken).toBeNull();
  });

  it("signs out from 'Forgot your PIN?', through the API", async () => {
    const api_ = lockedApp(() => json(204));
    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );
    await screen.findByRole("dialog");

    await userEvent.click(
      screen.getByRole("button", { name: "Forgot your PIN? Sign out" }),
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(api_.sent()).toContain("POST /v1/auth/logout");
  });

  it("comes back after five minutes hidden, not a moment before", async () => {
    lockedApp(() => json(204));
    let now = 1_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    let hidden = false;
    vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
    function setHidden(value: boolean) {
      hidden = value;
      act(() => {
        document.dispatchEvent(new Event("visibilitychange"));
      });
    }
    renderGate(
      <AppGate>
        <Secret />
      </AppGate>,
    );
    await screen.findByRole("dialog");
    await enter("4829");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );

    setHidden(true);
    now += RELOCK_AFTER_HIDDEN_MS - 1;
    setHidden(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    setHidden(true);
    now += RELOCK_AFTER_HIDDEN_MS;
    setHidden(false);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("is five minutes", () => {
    expect(RELOCK_AFTER_HIDDEN_MS).toBe(5 * 60 * 1000);
  });
});
