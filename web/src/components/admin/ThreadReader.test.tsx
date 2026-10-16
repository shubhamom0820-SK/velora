import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { fakeApi, json } from "@/lib/testing/fakeApi";

import { ThreadReader } from "./ThreadReader";

const REASON = "Reviewing the harassment report.";

function message(overrides: Record<string, unknown>) {
  return {
    id: "x",
    sender_id: "m1",
    kind: "text",
    body: null,
    masked: false,
    duration_s: null,
    audio_url: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderReader(reportId?: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ThreadReader id="t1" reportId={reportId} />
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

describe("a chat as staff read it (D-924)", () => {
  it("asks nothing until staff say why, then sends the reason", async () => {
    const api = fakeApi({
      "GET /v1/admin/threads/t1/messages": () =>
        json(200, {
          items: [
            message({ id: "a", body: "call me on 9812345678", masked: true }),
            message({
              id: "b",
              kind: "voice",
              duration_s: 7,
              audio_url: "https://media.test/v",
            }),
          ],
          next_cursor: null,
        }),
    });
    renderReader();
    const read = screen.getByRole("button", { name: t("admin.thread.read") });

    await userEvent.type(
      screen.getByLabelText(t("admin.thread.reason")),
      "too short",
    );
    expect(read).toBeDisabled();
    expect(api.calls).toEqual([]);
    await userEvent.clear(screen.getByLabelText(t("admin.thread.reason")));
    await userEvent.type(
      screen.getByLabelText(t("admin.thread.reason")),
      REASON,
    );
    await userEvent.click(read);

    expect(
      await screen.findByText("call me on 9812345678"),
    ).toBeInTheDocument();
    expect(screen.getByText(t("admin.thread.masked"))).toBeInTheDocument();
    expect(
      screen.getByText(t("admin.thread.voice", { seconds: 7 })),
    ).toBeInTheDocument();
    expect(api.calls[0]?.query.get("reason")).toBe(REASON);
  });

  it("starts the reason with the report it came from", () => {
    fakeApi({});
    renderReader("r1");

    expect(screen.getByLabelText(t("admin.thread.reason"))).toHaveValue(
      "Report r1: ",
    );
  });
});
