import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "@/lib/testing/fakeApi";
import { resetSession } from "@/store/session";

import AuthGroupLayout from "../layout";
import LoginPage from "./page";

const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: vi.fn() }),
  usePathname: () => "/login",
}));

/** /login as it's served: inside `(auth)`'s layout, which restores. */
function renderLogin() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AuthGroupLayout>
        <LoginPage />
      </AuthGroupLayout>
    </QueryClientProvider>,
  );
}

/** A refresh answered only when the test says, as from Singapore. */
function heldRefresh() {
  let answer: (response: Response) => void = () => undefined;
  const response = new Promise<Response>((resolve) => {
    answer = resolve;
  });
  return { route: () => response, answer: (r: Response) => answer(r) };
}

const sendCode = () => screen.getByRole("button", { name: "Send code" });

/** A number, a tap and Enter: each must send nothing while restoring. */
async function tryToSend() {
  await userEvent.type(screen.getByLabelText("Mobile number"), "9876543210");
  await userEvent.click(sendCode());
  await userEvent.type(screen.getByLabelText("Mobile number"), "{Enter}");
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  vi.stubEnv("SIGN_IN_PATH", "otp");
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

describe("/login sends a code only once the restore has settled (P-850, D-950)", () => {
  it("sends nothing while the restore is on its way, then sends once the API says there's none", async () => {
    const refresh = heldRefresh();
    const api_ = fakeApi({
      "POST /v1/auth/refresh": refresh.route,
      "POST /v1/auth/otp/send": () => json(200, { resend_after_s: 45 }),
    });
    renderLogin();

    await tryToSend();

    expect(sendCode()).toHaveAttribute("aria-busy", "true");
    expect(api_.sent()).toEqual(["POST /v1/auth/refresh"]);

    refresh.answer(envelope(401, "AUTH_REQUIRED"));
    await waitFor(() => expect(sendCode()).not.toHaveAttribute("aria-busy"));
    await userEvent.click(sendCode());

    await screen.findByRole("heading", { name: "Enter the code" });
    expect(api_.sent()).toEqual([
      "POST /v1/auth/refresh",
      "POST /v1/auth/otp/send",
    ]);
  });

  it.each([
    ["no signal", () => Promise.reject(new TypeError("Failed to fetch"))],
    ["a 503", () => envelope(503, "UNAVAILABLE")],
  ])(
    "still sends when the restore failed for %s, which says nothing about a session",
    async (_, route) => {
      const api_ = fakeApi({
        "POST /v1/auth/refresh": route,
        "POST /v1/auth/otp/send": () => json(200, { resend_after_s: 45 }),
      });
      renderLogin();

      await waitFor(() => expect(sendCode()).not.toHaveAttribute("aria-busy"));
      await userEvent.type(
        screen.getByLabelText("Mobile number"),
        "9876543210",
      );
      await userEvent.click(sendCode());

      await screen.findByRole("heading", { name: "Enter the code" });
      expect(api_.sent()).toContain("POST /v1/auth/otp/send");
    },
  );

  it("never sends for someone whose session restores, and moves them on", async () => {
    const refresh = heldRefresh();
    const api_ = fakeApi({
      "POST /v1/auth/refresh": refresh.route,
      "GET /v1/me": () =>
        json(200, { id: "u1", onboarding_step: "dob", profile: {} }),
      "POST /v1/auth/otp/send": () => json(200, { resend_after_s: 45 }),
    });
    renderLogin();

    await tryToSend();
    refresh.answer(json(200, { access_token: "t" }));

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/onboarding/birthday"),
    );
    await userEvent.click(sendCode());
    expect(sendCode()).toHaveAttribute("aria-busy", "true");
    expect(api_.sent()).toEqual(["POST /v1/auth/refresh", "GET /v1/me"]);
  });
});
