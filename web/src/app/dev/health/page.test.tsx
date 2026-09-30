import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import DevHealthPage from "./page";

const fetchMock = vi.fn<typeof fetch>();

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  // No retries here: the error state should show on the first failure.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      {DevHealthPage()}
    </QueryClientProvider>,
  );
}

describe("/dev/health", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it.each(["production", "test"])("is not found when NODE_ENV is %s", (env) => {
    vi.stubEnv("NODE_ENV", env);

    expect(() => DevHealthPage()).toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
  });

  it("shows loading, then the API's answer", async () => {
    vi.stubEnv("NODE_ENV", "development");
    fetchMock.mockResolvedValue(json(200, { status: "ok" }));

    renderPage();

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      "https://api.test/healthz",
    );
  });

  it("shows the error, and Try again asks again", async () => {
    vi.stubEnv("NODE_ENV", "development");
    fetchMock
      .mockResolvedValueOnce(
        json(500, { error: { code: "INTERNAL", message: "Boom." } }),
      )
      .mockResolvedValueOnce(json(200, { status: "ok" }));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "INTERNAL (500)",
    );

    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));

    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
