import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { fakeApi, json } from "@/lib/testing/fakeApi";

import { MinorFlagList } from "./MinorFlagList";

function flagged(id: string) {
  const at = new Date().toISOString();
  return {
    user: {
      id,
      first_name: `Person ${id}`,
      username: null,
      city: null,
      gender: "female",
      age: 19,
      role: "user",
      status: "active",
      onboarding_step: "done",
      erased: false,
      deleted_requested_at: null,
      last_active_at: null,
      created_at: at,
    },
    flags: 3,
    scores: [0.4, 0.5, 0.93],
    times: [at, at, at],
    first_at: at,
    last_at: at,
  };
}

function renderList() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MinorFlagList />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the possible-minor list (P-72)", () => {
  it("links each person to their page, with their flags and scores", async () => {
    fakeApi({
      "GET /v1/admin/minor-flags": () =>
        json(200, { items: [flagged("a")], next_cursor: null }),
    });

    renderList();

    const link = await screen.findByRole("link", { name: "Person a" });
    expect(link).toHaveAttribute("href", "/admin/users/a");
    expect(
      screen.getByText(
        t("admin.minorFlags.flags", { count: 3, scores: "0.40, 0.50, 0.93" }),
        { exact: false },
      ),
    ).toBeInTheDocument();
  });

  it("says when nobody is waiting", async () => {
    fakeApi({
      "GET /v1/admin/minor-flags": () =>
        json(200, { items: [], next_cursor: null }),
    });

    renderList();

    expect(
      await screen.findByText(t("admin.minorFlags.empty")),
    ).toBeInTheDocument();
  });
});
