import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t, type MessageKey } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { ClaimForm } from "./ClaimForm";

const PAYMENT = "5b0d5f8e-2c4a-4d0e-9a0b-1f1e1d1c1b1a";

function renderClaim(route: Route) {
  const api = fakeApi({ "POST /v1/refund-requests": route });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.wallet(), { balance: 5 });
  const onDone = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ClaimForm paymentId={PAYMENT} onDone={onDone} />
    </QueryClientProvider>,
  );
  return { api, client, onDone };
}

const send = () =>
  userEvent.click(
    screen.getByRole("button", { name: t("wallet.store.claim.send") }),
  );

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("a broken payment's claim (P-481, D-580)", () => {
  it("offers the two kinds only, never a change of mind, and says purchases are final", () => {
    renderClaim(() => json(201, {}));

    expect(
      screen.getAllByRole("radio").map((radio) => radio.getAttribute("value")),
    ).toEqual(["missing_velas", "duplicate_charge"]);
    expect(
      screen.getByRole("radio", {
        name: t("wallet.store.claim.missing_velas"),
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", {
        name: t("wallet.store.claim.duplicate_charge"),
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(t("wallet.store.claim.final"))).toBeInTheDocument();
  });

  it("sends nothing until a kind is chosen", () => {
    renderClaim(() => json(201, {}));

    expect(
      screen.getByRole("button", { name: t("wallet.store.claim.send") }),
    ).toBeDisabled();
  });

  it.each(["missing_velas", "duplicate_charge"] as const)(
    "sends the payment and %s, nothing else, then says what happens next",
    async (reason) => {
      const { api, onDone } = renderClaim(() =>
        json(201, {
          id: "c1",
          payment_id: PAYMENT,
          reason,
          status: "open",
          created_at: "2026-10-09T10:00:00Z",
        }),
      );

      await userEvent.click(
        screen.getByRole("radio", { name: t(`wallet.store.claim.${reason}`) }),
      );
      await send();

      expect(api.calls.map((call) => call.body)).toEqual([
        { payment_id: PAYMENT, reason },
      ]);
      const sent = await screen.findByRole("status");
      expect(sent).toHaveTextContent(t("wallet.store.claim.sentTitle"));
      expect(sent).toHaveTextContent(t("wallet.store.claim.sentBody"));
      await userEvent.click(
        screen.getByRole("button", { name: t("wallet.store.close") }),
      );
      expect(onDone).toHaveBeenCalled();
    },
  );

  it.each<[string, Route, MessageKey]>([
    [
      "ALREADY_EXISTS",
      () => envelope(409, "ALREADY_EXISTS"),
      "wallet.store.claim.already",
    ],
    [
      "NOT_ALLOWED, velas_granted",
      () => envelope(403, "NOT_ALLOWED", { why: "velas_granted" }),
      "wallet.store.claim.granted",
    ],
    [
      "NOT_FOUND",
      () => envelope(404, "NOT_FOUND"),
      "wallet.store.claim.notFound",
    ],
    [
      "RATE_LIMITED",
      () => envelope(429, "RATE_LIMITED"),
      "wallet.store.claim.tooMany",
    ],
    ["a 500", () => envelope(500, "INTERNAL"), "wallet.store.claim.failed"],
  ])(
    "refused with %s, it says so in his words",
    async (_code, route, words) => {
      renderClaim(route);

      await userEvent.click(
        screen.getByRole("radio", {
          name: t("wallet.store.claim.missing_velas"),
        }),
      );
      await send();

      expect(await screen.findByRole("alert")).toHaveTextContent(t(words));
      expect(screen.queryByText(t("wallet.store.claim.sentTitle"))).toBeNull();
    },
  );

  it("Velas granted after all: the balance is asked again, so it shows them", async () => {
    const { client } = renderClaim(() =>
      envelope(403, "NOT_ALLOWED", { why: "velas_granted" }),
    );

    await userEvent.click(
      screen.getByRole("radio", {
        name: t("wallet.store.claim.missing_velas"),
      }),
    );
    await send();
    await screen.findByRole("alert");

    expect(client.getQueryState(queryKeys.wallet())?.isInvalidated).toBe(true);
  });
});
