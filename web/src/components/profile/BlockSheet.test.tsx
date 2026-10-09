import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { BlockSheet } from "./BlockSheet";

const BLOCKED = {
  user: {
    id: "u2",
    first_name: "Simran",
    username: "simran.k",
    main_photo_url: null,
    shows_badge: false,
    is_online: false,
    deleted: false,
  },
  blocked_at: "2026-10-09T05:00:00Z",
};

function renderSheet() {
  const onClose = vi.fn();
  const onBlocked = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <BlockSheet
          open
          userId="u2"
          firstName="Simran"
          onClose={onClose}
          onBlocked={onBlocked}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { onClose, onBlocked };
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the block sheet (T-9.1)", () => {
  it("says what a block does, and that they're never told", () => {
    fakeApi({});
    renderSheet();

    for (const line of [
      t("profile.blockTheyWont", { app: APP_NAME }),
      t("profile.blockYouWont"),
      t("profile.blockThreads"),
      t("profile.blockSilent"),
      // P-762, with T-9.8's blocked list.
      t("profile.blockUndo"),
    ]) {
      expect(screen.getByText(line)).toBeVisible();
    }
  });

  it("blocks on the confirm, then says so to the screen", async () => {
    const api = fakeApi({ "POST /v1/blocks": () => json(201, BLOCKED) });
    const { onBlocked } = renderSheet();

    await userEvent.click(
      screen.getByRole("button", {
        name: t("profile.block", { name: "Simran" }),
      }),
    );

    await vi.waitFor(() => expect(onBlocked).toHaveBeenCalledOnce());
    expect(api.calls.map((call) => [call.path, call.body])).toEqual([
      ["/v1/blocks", { user_id: "u2" }],
    ]);
  });

  it("cancels with nothing sent", async () => {
    const api = fakeApi({});
    const { onClose } = renderSheet();

    await userEvent.click(
      screen.getByRole("button", { name: t("profile.blockCancel") }),
    );

    expect(onClose).toHaveBeenCalledOnce();
    expect(api.calls).toEqual([]);
  });

  it("says when blocking failed, and stays", async () => {
    fakeApi({ "POST /v1/blocks": () => envelope(500, "INTERNAL") });
    const { onBlocked } = renderSheet();

    await userEvent.click(
      screen.getByRole("button", {
        name: t("profile.block", { name: "Simran" }),
      }),
    );

    expect(
      await screen.findByText(t("profile.blockFailed", { name: "Simran" })),
    ).toBeVisible();
    expect(onBlocked).not.toHaveBeenCalled();
  });
});
