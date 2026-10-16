import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { ReportSheet } from "./ReportSheet";

const FILED = { id: "r1", created_at: "2026-10-09T05:00:00Z" };

function renderSheet(onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ReportSheet open userId="u2" firstName="Simran" onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onClose, dialog: () => screen.getByRole("dialog") };
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the report sheet (T-9.1)", () => {
  it("asks for a reason first, then sends it with also-block on as it starts", async () => {
    const api = fakeApi({ "POST /v1/reports": () => json(201, FILED) });
    const { onClose } = renderSheet();

    const send = screen.getByRole("button", { name: t("profile.reportPick") });
    expect(send).toBeDisabled();
    expect(
      screen.getByRole("checkbox", {
        name: t("profile.alsoBlock", { name: "Simran" }),
      }),
    ).toBeChecked();
    await userEvent.click(
      screen.getByRole("radio", { name: t("profile.reason.harass") }),
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: t("profile.reportDetails") }),
      "  Abusive after I said no.  ",
    );
    await userEvent.click(
      screen.getByRole("button", { name: t("profile.reportSend") }),
    );

    const sent = await screen.findByRole("status");
    expect(within(sent).getByText(t("profile.reportSentTitle"))).toBeVisible();
    expect(within(sent).getByText(t("profile.reportSentBody"))).toBeVisible();
    // P-761: the review the queue's 24-hour timer makes happen (T-9.5),
    // in its words, read as the literal so a change of copy shows here.
    expect(sent).toHaveTextContent("A moderator reviews this within 24 hours.");
    expect(api.calls.map((call) => call.body)).toEqual([
      {
        reported_id: "u2",
        reason: "harass",
        also_block: true,
        details: "Abusive after I said no.",
      },
    ]);
    await userEvent.click(
      within(sent).getByRole("button", { name: t("profile.reportDone") }),
    );
    expect(onClose).toHaveBeenCalledWith(true);
  });

  it("sends no details when none are written, and says it didn't block", async () => {
    const api = fakeApi({ "POST /v1/reports": () => json(201, FILED) });
    const { onClose } = renderSheet();

    await userEvent.click(
      screen.getByRole("radio", { name: t("profile.reason.fake") }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: t("profile.alsoBlock", { name: "Simran" }),
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: t("profile.reportSend") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: t("profile.reportDone") }),
    );

    expect(api.calls[0]?.body).toEqual({
      reported_id: "u2",
      reason: "fake",
      also_block: false,
    });
    expect(onClose).toHaveBeenCalledWith(false);
  });

  it("caps what she writes at 500 characters", () => {
    fakeApi({});
    renderSheet();

    expect(
      screen.getByRole("textbox", { name: t("profile.reportDetails") }),
    ).toHaveAttribute("maxLength", "500");
  });

  it("says when the day's reports are used up, and when sending failed", async () => {
    let answer = envelope(429, "RATE_LIMITED", { retry_after_s: 3600 });
    fakeApi({ "POST /v1/reports": () => answer });
    renderSheet();
    await userEvent.click(
      screen.getByRole("radio", { name: t("profile.reason.other") }),
    );
    const send = screen.getByRole("button", { name: t("profile.reportSend") });

    await userEvent.click(send);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("profile.reportTooMany"),
    );

    answer = envelope(500, "INTERNAL");
    await userEvent.click(send);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("profile.reportFailed"),
    );
  });

  it("never says they're told, and promises only the queue's 24 hours", () => {
    fakeApi({});
    renderSheet();

    const copy = [
      t("profile.reportIntro"),
      t("profile.reportSentBody"),
      t("profile.reportSentTitle"),
    ].join(" ");
    // P-761: from T-9.5 the queue's 24-hour timer exists, so the sheet says
    // so, in its words, and promises nothing sooner (D-863 until then).
    expect(copy.match(/hours?|minutes?|today|soon/gi)).toEqual(["hours"]);
    expect(copy).toMatch(/within 24 hours/);
    expect(copy).toMatch(/never told/);
  });
});
