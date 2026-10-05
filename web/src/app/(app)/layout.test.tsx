import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "@/lib/testing/fakeApi";
import { resetSession } from "@/store/session";

import AppGroupLayout from "./layout";

const nav = vi.hoisted(() => ({ replace: vi.fn(), pathname: "/discover" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => nav.pathname,
}));

function me(onboarding_step: string, has_pin = false) {
  return { id: "u1", onboarding_step, has_pin, profile: { location: "fresh" } };
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AppGroupLayout>
        <p>A screen</p>
      </AppGroupLayout>
    </QueryClientProvider>,
  );
}

const shellNav = () =>
  screen.queryByRole("navigation", { name: t("shell.nav") });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  setCookie("csrf_local", "c1");
  nav.replace.mockReset();
  nav.pathname = "/discover";
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

// T-5.6 adds the header and nav inside T-3.10's gate and lock, never replacing
// them: the shell shows only once the gate lets someone in.
describe("the app's layout (T-3.10, T-5.6)", () => {
  it("shows the shell around the screen once a finished onboarding is let in", async () => {
    fakeApi({
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
      "GET /v1/me": () => json(200, me("done")),
    });

    renderApp();

    expect(await screen.findByText("A screen")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveTextContent("A screen");
    expect(shellNav()).toBeInTheDocument();
    expect(screen.getByRole("banner")).toContainElement(shellNav());
  });

  it("shows no shell while the session is restored, nor to someone signed out", async () => {
    let answer: (response: Response) => void = () => {};
    fakeApi({
      "POST /v1/auth/refresh": () =>
        new Promise<Response>((resolve) => {
          answer = resolve;
        }),
    });

    renderApp();

    expect(await screen.findByRole("status")).toBeInTheDocument();
    expect(shellNav()).not.toBeInTheDocument();

    answer(envelope(401, "AUTH_REQUIRED"));

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    expect(shellNav()).not.toBeInTheDocument();
    expect(screen.queryByText("A screen")).not.toBeInTheDocument();
  });

  it("shows no shell to an unfinished onboarding, sent to its step", async () => {
    fakeApi({
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
      "GET /v1/me": () => json(200, me("seeking")),
    });

    renderApp();

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/looking-for"),
    );
    expect(shellNav()).not.toBeInTheDocument();
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
  });

  it("puts the PIN lock over the shell, which is inert behind it", async () => {
    fakeApi({
      "POST /v1/auth/refresh": () => json(200, { access_token: "t" }),
      "GET /v1/me": () => json(200, me("done", true)),
    });

    renderApp();

    expect(await screen.findByRole("dialog")).toHaveAccessibleName(
      "Enter your PIN",
    );
    const shell = screen.getByRole("banner");
    expect(shell.closest("[inert]")).not.toBeNull();
    expect(screen.getByRole("dialog").closest("[inert]")).toBeNull();
  });
});
