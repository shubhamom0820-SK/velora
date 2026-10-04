import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "@/lib/testing/fakeApi";
import { resetSession } from "@/store/session";

import AuthGroupLayout from "./layout";
import OnboardingLayout from "./onboarding/layout";

const nav = vi.hoisted(() => ({ replace: vi.fn(), pathname: "/login" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => nav.pathname,
}));

function renderAuth(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AuthGroupLayout>{children}</AuthGroupLayout>
    </QueryClientProvider>,
  );
}

// Nothing of the app shell (T-5.6): no header, no nav, none of its links.
function expectNoShell() {
  expect(screen.queryByRole("banner")).not.toBeInTheDocument();
  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
  nav.replace.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

// The header and nav belong to (app) only. Onboarding keeps T-3.11's
// StepFrame, with no header or nav, as in the prototype.
describe("the sign-in layouts (T-5.6)", () => {
  it("never put the app shell on /login", async () => {
    nav.pathname = "/login";
    fakeApi({ "POST /v1/auth/refresh": () => envelope(401, "AUTH_REQUIRED") });

    renderAuth(<p>Sign in</p>);

    expect(await screen.findByText("Sign in")).toBeInTheDocument();
    expectNoShell();
  });

  it("never put the app shell on an onboarding step", async () => {
    nav.pathname = "/onboarding/name";
    fakeApi({
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
      "GET /v1/me": () =>
        json(200, { id: "u1", onboarding_step: "profile", has_pin: false }),
    });

    renderAuth(
      <OnboardingLayout>
        <p>A step</p>
      </OnboardingLayout>,
    );

    expect(await screen.findByText("A step")).toBeInTheDocument();
    expectNoShell();
  });
});
