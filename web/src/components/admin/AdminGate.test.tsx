import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { Component, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionRestorer } from "@/components/session/SessionRestorer";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "@/lib/testing/fakeApi";
import { resetSession } from "@/store/session";

import { AdminGate } from "./AdminGate";

const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => "/admin",
  // As Next's: it throws, and the nearest not-found boundary draws the 404.
  notFound: () => {
    throw new Error("NEXT_HTTP_ERROR_FALLBACK;404");
  },
}));

/** Stands in for Next's not-found boundary. */
class NotFoundBoundary extends Component<
  { children: ReactNode },
  { missing: boolean }
> {
  state = { missing: false };
  static getDerivedStateFromError() {
    return { missing: true };
  }
  render() {
    return this.state.missing ? <p>404 page</p> : this.props.children;
  }
}

function renderGate() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SessionRestorer />
      <NotFoundBoundary>
        <AdminGate>
          <p>The panel</p>
        </AdminGate>
      </NotFoundBoundary>
    </QueryClientProvider>,
  );
}

function signedInAs(role: string) {
  fakeApi({
    "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
    "GET /v1/me": () =>
      json(200, { id: "u1", role, has_pin: false, onboarding_step: "dob" }),
  });
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
  nav.replace.mockReset();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

describe("the admin gate (T-9.5, P-30)", () => {
  it.each(["moderator", "admin"])(
    "lets a %s in, onboarded or not",
    async (role) => {
      signedInAs(role);

      renderGate();

      expect(await screen.findByText("The panel")).toBeInTheDocument();
      expect(nav.replace).not.toHaveBeenCalled();
    },
  );

  it("shows anyone else the 404 page, and nothing behind it", async () => {
    signedInAs("user");

    renderGate();

    expect(await screen.findByText("404 page")).toBeInTheDocument();
    expect(screen.queryByText("The panel")).not.toBeInTheDocument();
  });

  it("sends someone with no session to /login", async () => {
    fakeApi({ "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED") });

    renderGate();

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("The panel")).not.toBeInTheDocument();
  });
});
