import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { fakeApi, json } from "@/lib/testing/fakeApi";

import { ClaimQueue } from "./ClaimQueue";

const NOTE = "The gateway shows one capture only.";

function renderQueue() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ClaimQueue />
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

describe("the claims screen (P-480)", () => {
  it("resolves a claim behind a confirmation, with its note", async () => {
    const api = fakeApi({
      "GET /v1/admin/refund-requests": () =>
        json(200, {
          items: [
            {
              id: "c1",
              user_id: "m1",
              payment_id: "p1",
              order_id: "order_1",
              payment_status: "paid",
              reason: "duplicate_charge",
              status: "open",
              note: null,
              provider_payment_id: null,
              provider_refund_id: null,
              created_at: new Date().toISOString(),
              resolved_at: null,
            },
          ],
          next_cursor: null,
        }),
      "POST /v1/admin/refund-requests/c1/resolve": () => json(200, {}),
    });
    renderQueue();

    await userEvent.click(
      await screen.findByRole("button", { name: t("admin.reports.resolve") }),
    );
    const sheet = screen.getByRole("dialog");
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("admin.claims.actions.reject"),
      }),
    );
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      NOTE,
    );
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("admin.reports.resolve") }),
    );

    await waitFor(() =>
      expect(api.calls.find((call) => call.method === "POST")?.body).toEqual({
        action: "reject",
        note: NOTE,
      }),
    );
  });

  it("says so when there are none", async () => {
    fakeApi({
      "GET /v1/admin/refund-requests": () =>
        json(200, { items: [], next_cursor: null }),
    });
    renderQueue();

    expect(
      await screen.findByText(t("admin.claims.empty")),
    ).toBeInTheDocument();
  });
});
