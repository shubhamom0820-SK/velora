import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";
import { useSession } from "@/store/session";

import { SignedInProfileRedirect } from "./SignedInProfileRedirect";

const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
}));

function renderRedirect(onboarding_step: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "u1", onboarding_step });
  return render(
    <QueryClientProvider client={client}>
      <SignedInProfileRedirect username="noor_s" />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  nav.replace.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  useSession.setState({ status: "unknown", accessToken: null });
});

describe("/@username for someone signed in (T-6.8)", () => {
  it("goes to the in-app profile by the id the username names", async () => {
    useSession.setState({ status: "signed-in", accessToken: "token" });
    fakeApi({
      "GET /v1/users/by-username/noor_s": () => json(200, { id: "u2" }),
    });

    renderRedirect("done");

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/people/u2"));
  });

  it("stays when the API won't show it to them", async () => {
    useSession.setState({ status: "signed-in", accessToken: "token" });
    const api = fakeApi({
      "GET /v1/users/by-username/noor_s": () => envelope(404, "NOT_FOUND"),
    });

    renderRedirect("done");

    await waitFor(() => expect(api.sent()).toHaveLength(1));
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("asks nothing for someone signed out", async () => {
    const api = fakeApi({});
    useSession.setState({ status: "signed-out", accessToken: null });

    renderRedirect("done");

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.sent()).toEqual([]);
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("asks nothing for someone still onboarding", async () => {
    const api = fakeApi({});
    useSession.setState({ status: "signed-in", accessToken: "token" });

    renderRedirect("photos");

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.sent()).toEqual([]);
    expect(nav.replace).not.toHaveBeenCalled();
  });
});
