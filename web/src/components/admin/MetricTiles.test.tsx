import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { MetricTiles } from "./MetricTiles";

function figures(revenue: unknown) {
  return {
    users_by_status: {
      active: 40,
      paused: 1,
      frozen: 2,
      banned: 1,
      deleted: 3,
    },
    signups_24h: 5,
    signups_7d: 21,
    reports_open: 4,
    oldest_open_report_at: null,
    photos_pending: 6,
    frozen: 2,
    claims_open: 1,
    revenue,
  };
}

function renderTiles() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MetricTiles />
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  act(() => focusManager.setFocused(undefined));
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the dashboard (D-926)", () => {
  it("shows money in when the API sends it, an admin's", async () => {
    fakeApi({
      "GET /v1/admin/metrics": () =>
        json(
          200,
          figures({
            last_7_days_paise: 4_990_00,
            last_30_days_paise: 9_980_00,
            financial_year: "2026-27",
            financial_year_paise: 19_960_00,
          }),
        ),
    });

    renderTiles();

    expect(
      await screen.findByText(t("admin.metrics.revenue")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("admin.metrics.rupees", { amount: "4,990" })),
    ).toBeInTheDocument();
  });

  it("shows no money for a moderator, whose revenue is null", async () => {
    fakeApi({ "GET /v1/admin/metrics": () => json(200, figures(null)) });

    renderTiles();

    expect(
      await screen.findByText(t("admin.metrics.reportsOpen")),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(t("admin.metrics.revenue")),
    ).not.toBeInTheDocument();
  });

  it("never asks again by itself when the window comes back: each read is audited", async () => {
    const api = fakeApi({
      "GET /v1/admin/metrics": () => json(200, figures(null)),
    });
    const client = renderTiles();
    await screen.findByText(t("admin.metrics.reportsOpen"));

    // Stale, as it is a minute on, but not asked again; then back to the window.
    await act(() =>
      client.invalidateQueries({
        queryKey: queryKeys.admin(),
        refetchType: "none",
      }),
    );
    act(() => focusManager.setFocused(false));
    act(() => focusManager.setFocused(true));
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(api.sent()).toEqual(["GET /v1/admin/metrics"]);
  });

  it("says so when it didn't load", async () => {
    fakeApi({ "GET /v1/admin/metrics": () => envelope(500, "INTERNAL") });

    renderTiles();

    expect(await screen.findByText(t("admin.failed"))).toBeInTheDocument();
  });
});
