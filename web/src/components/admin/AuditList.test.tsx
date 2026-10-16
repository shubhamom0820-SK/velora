import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { fakeApi, json } from "@/lib/testing/fakeApi";

import { AuditList } from "./AuditList";

function renderList() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AuditList />
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

describe("the audit log (T-9.5)", () => {
  it("names the system user as System, and filters by one action", async () => {
    const api = fakeApi({
      "GET /v1/admin/audit": () =>
        json(200, {
          items: [
            {
              id: "a1",
              actor_id: "00000000-0000-4000-8000-000000000001",
              actor_is_system: true,
              action: "fraud.freeze",
              target_type: "user",
              target_id: "u1",
              meta: { rule: "score", score: 85 },
              created_at: new Date().toISOString(),
            },
          ],
          next_cursor: null,
        }),
    });
    renderList();

    expect(
      await screen.findByText(t("admin.audit.system"), { exact: false }),
    ).toBeInTheDocument();
    await userEvent.type(
      screen.getByLabelText(t("admin.audit.filter")),
      "fraud.freeze",
    );
    await userEvent.click(
      screen.getByRole("button", { name: t("admin.audit.filter") }),
    );

    await waitFor(() =>
      expect(api.calls.at(-1)?.query.get("action")).toBe("fraud.freeze"),
    );
  });

  it("says so when nothing is recorded", async () => {
    fakeApi({
      "GET /v1/admin/audit": () => json(200, { items: [], next_cursor: null }),
    });
    renderList();

    expect(await screen.findByText(t("admin.audit.empty"))).toBeInTheDocument();
  });
});
