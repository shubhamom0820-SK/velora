import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { fakeApi, json } from "@/lib/testing/fakeApi";

import { FeedRow } from "./FeedRow";

function renderRow() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <FeedRow
        feed="foryou"
        onFeed={() => {}}
        filterCount={0}
        onFilters={() => {}}
      />
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

describe("the feed row's Liked you (T-6.7, P-443)", () => {
  it("links to Liked you with how many are waiting", async () => {
    fakeApi({ "GET /v1/likes/count": () => json(200, { count: 3 }) });
    renderRow();

    const link = await screen.findByRole("link", {
      name: t("likes.entryCount", { count: 3 }),
    });
    expect(link).toHaveAttribute("href", "/discover/likes");
    expect(link).toHaveTextContent("3");
  });

  it("shows no count when nobody is waiting", async () => {
    fakeApi({ "GET /v1/likes/count": () => json(200, { count: 0 }) });
    renderRow();

    expect(
      await screen.findByRole("link", { name: t("likes.entry") }),
    ).toHaveAttribute("href", "/discover/likes");
  });
});
