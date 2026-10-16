import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { fakeApi, json } from "@/lib/testing/fakeApi";

import { FreezeList } from "./FreezeList";

function freeze(id: string, automatic: boolean) {
  return {
    user: {
      id,
      first_name: `Person ${id}`,
      username: null,
      city: null,
      gender: "female",
      age: 24,
      role: "user",
      status: "frozen",
      onboarding_step: "done",
      erased: false,
      deleted_requested_at: null,
      last_active_at: null,
      created_at: new Date().toISOString(),
    },
    frozen_at: new Date().toISOString(),
    automatic,
    rule: automatic ? "reports" : null,
    score: automatic ? 81 : null,
  };
}

function renderList(role: "moderator" | "admin") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "s1", role });
  render(
    <QueryClientProvider client={client}>
      <FreezeList />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  fakeApi({
    "GET /v1/admin/freezes": () =>
      json(200, {
        items: [freeze("a", true), freeze("b", false)],
        next_cursor: null,
      }),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("who is frozen now (P-800)", () => {
  it("marks the automatic ones with their rule and score", async () => {
    renderList("moderator");

    expect(
      await screen.findByText(
        t("admin.freezes.automatic", { rule: "reports", score: 81 }),
        {
          exact: false,
        },
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("admin.freezes.manual"), { exact: false }),
    ).toBeInTheDocument();
  });

  it("offers the unfreeze to an admin only", async () => {
    renderList("moderator");
    await screen.findByText(t("admin.freezes.manual"), { exact: false });
    expect(
      screen.queryByRole("button", { name: t("admin.freezes.unfreeze") }),
    ).not.toBeInTheDocument();
  });

  it("offers it to an admin", async () => {
    renderList("admin");

    expect(
      await screen.findAllByRole("button", {
        name: t("admin.freezes.unfreeze"),
      }),
    ).toHaveLength(2);
  });
});
