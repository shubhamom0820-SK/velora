import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { creditsText } from "@/lib/credits";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { AlbumSection } from "./AlbumSection";

// Not D-231's 1 Vela: a price written into the code would still say 1.
const PRICE = 3;

function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/users/u2/album": () => json(200, { status: null, photos: [] }),
    "GET /v1/prices": () => json(200, { album_request: PRICE, super_like: 5 }),
    "GET /v1/wallet": () => json(200, { balance: 10 }),
    "GET /v1/users/u2": () => json(200, {}),
    ...overrides,
  });
}

function renderAlbum(gender: "male" | "female" = "male") {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  client.setQueryData(queryKeys.me(), { id: "u1", gender });
  client.setQueryData(queryKeys.profile("u2"), { id: "u2" });
  const view = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AlbumSection id="u2" count={2} own={false} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

const askFor = (price: string) =>
  screen.findByRole("button", { name: t("profile.albumAsk", { price }) });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the album row (T-8.8, D-732)", () => {
  it("shows a man the lock and the price from /prices, and sends that price", async () => {
    let asked = false;
    const api = routes({
      "GET /v1/users/u2/album": () =>
        json(200, { status: asked ? "pending" : null, photos: [] }),
      "POST /v1/album-requests": (call) => {
        // The price this row showed, exactly (P-56, D-600).
        expect(call.body).toEqual({ owner_id: "u2", shown_price: PRICE });
        asked = true;
        return json(201, {});
      },
    });
    renderAlbum();

    expect(
      screen.getByText(t("profile.albumOther", { count: 2 })),
    ).toBeInTheDocument();
    await userEvent.click(await askFor(creditsText(PRICE)));

    expect(await screen.findByText(t("profile.albumSent"))).toBeInTheDocument();
    expect(
      await screen.findByText(t("profile.albumPending")),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("POST /v1/album-requests");
  });

  it("shows a woman Free, sends 0 and never asks for prices", async () => {
    const api = routes({
      "POST /v1/album-requests": (call) => {
        expect(call.body).toEqual({ owner_id: "u2", shown_price: 0 });
        return json(201, {});
      },
    });
    renderAlbum("female");

    await userEvent.click(await askFor(t("wallet.free")));

    await waitFor(() =>
      expect(api.sent()).toContain("POST /v1/album-requests"),
    );
    expect(api.sent()).not.toContain("GET /v1/prices");
  });

  it("shows no button while the price is unknown, or the action is off", async () => {
    const api = routes({
      "GET /v1/prices": () => json(200, { super_like: 5 }),
    });
    renderAlbum();

    await waitFor(() =>
      expect(api.sent()).toEqual(
        expect.arrayContaining(["GET /v1/prices", "GET /v1/users/u2/album"]),
      ),
    );
    await waitFor(() =>
      expect(document.querySelector("[aria-busy='true']")).toBeNull(),
    );
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says a request is waiting, with no button", async () => {
    routes({
      "GET /v1/users/u2/album": () =>
        json(200, { status: "pending", photos: [] }),
    });
    renderAlbum();

    expect(
      await screen.findByText(t("profile.albumPending")),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows his own copies once granted, with the watermark note", async () => {
    const urls = [
      "http://127.0.0.1:9000/velora-private/album/r1/p1.jpg?sig=1",
      "http://127.0.0.1:9000/velora-private/album/r1/p2.jpg?sig=2",
    ];
    routes({
      "GET /v1/users/u2/album": () =>
        json(200, { status: "granted", photos: urls.map((url) => ({ url })) }),
    });
    renderAlbum();

    expect(
      await screen.findByRole("img", {
        name: t("profile.albumPhoto", { n: 2, total: 2 }),
      }),
    ).toHaveAttribute("src", urls[1]);
    expect(screen.getByText(t("profile.albumNote"))).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the copies are being made while a grant has none yet", async () => {
    routes({
      "GET /v1/users/u2/album": () =>
        json(200, { status: "granted", photos: [] }),
    });
    renderAlbum();

    expect(
      await screen.findByText(t("profile.albumPreparing")),
    ).toBeInTheDocument();
  });

  it.each(["declined", "revoked"])(
    "reads %s exactly as locked, never naming it (D-230)",
    async (status) => {
      routes({
        "GET /v1/users/u2/album": () => json(200, { status, photos: [] }),
      });
      const { container } = renderAlbum();

      expect(await askFor(creditsText(PRICE))).toBeInTheDocument();
      expect(container.textContent).not.toMatch(/declin|revok/i);
    },
  );

  it("says recently_declined in neutral words, never its code", async () => {
    routes({
      "POST /v1/album-requests": () =>
        envelope(422, "NOT_ALLOWED", { why: "recently_declined" }),
    });
    renderAlbum();

    await userEvent.click(await askFor(creditsText(PRICE)));

    expect(
      await screen.findByText(t("profile.albumTooSoon")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/recently_declined|NOT_ALLOWED/)).toBeNull();
  });

  it("says an empty album in words, and asks for the profile again", async () => {
    routes({
      "POST /v1/album-requests": () =>
        envelope(422, "NOT_ALLOWED", { why: "empty_album" }),
    });
    const { client } = renderAlbum();

    await userEvent.click(await askFor(creditsText(PRICE)));

    expect(
      await screen.findByText(t("profile.albumEmpty")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/empty_album/)).toBeNull();
    // Its count was more than there is to see: the profile is asked again.
    expect(client.getQueryState(queryKeys.profile("u2"))?.isInvalidated).toBe(
      true,
    );
  });

  it("says the new price when it changed, and asks /prices again", async () => {
    let price = PRICE;
    const api = routes({
      "GET /v1/prices": () => json(200, { album_request: price }),
      "POST /v1/album-requests": () => {
        price = 4;
        return envelope(409, "PRICE_CHANGED", { price: 4 });
      },
    });
    renderAlbum();

    await userEvent.click(await askFor(creditsText(PRICE)));

    expect(
      await screen.findByText(
        t("profile.albumPriceChanged", { velas: creditsText(4) }),
      ),
    ).toBeInTheDocument();
    expect(await askFor(creditsText(4))).toBeInTheDocument();
    // Nothing tried again by itself.
    expect(
      api.sent().filter((sent) => sent === "POST /v1/album-requests"),
    ).toHaveLength(1);
  });

  it("opens the store sheet when he can't afford it, with no toast", async () => {
    routes({
      "POST /v1/album-requests": () => envelope(402, "INSUFFICIENT_CREDITS"),
    });
    renderAlbum();

    await userEvent.click(await askFor(creditsText(PRICE)));

    await waitFor(() => expect(useStoreSheet.getState().open).toBe(true));
    expect(screen.queryByText(t("profile.albumFailed"))).toBeNull();
  });

  it("says a profile it may no longer reach can't be asked", async () => {
    routes({
      "POST /v1/album-requests": () => envelope(404, "NOT_FOUND"),
    });
    renderAlbum();

    await userEvent.click(await askFor(creditsText(PRICE)));

    expect(
      await screen.findByText(t("profile.albumUnavailable")),
    ).toBeInTheDocument();
  });

  it("says when the album failed to load, and tries again", async () => {
    let fail = true;
    routes({
      "GET /v1/users/u2/album": () =>
        fail
          ? envelope(500, "INTERNAL")
          : json(200, { status: "pending", photos: [] }),
    });
    renderAlbum();

    expect(
      await screen.findByText(t("profile.albumLoadFailed"), undefined, {
        timeout: 5000,
      }),
    ).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));

    expect(
      await screen.findByText(t("profile.albumPending")),
    ).toBeInTheDocument();
  });
});
