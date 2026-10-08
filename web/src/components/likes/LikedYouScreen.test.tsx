import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { creditsText } from "@/lib/credits";
import type { LikeCard } from "@/lib/queries/likes";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { LikedYouScreen } from "./LikedYouScreen";

const BLUR = "https://cdn.test/b/0b7a2f1e.jpg";

function hidden(overrides: Partial<LikeCard> = {}): LikeCard {
  return {
    handle: "a".repeat(32),
    is_super: false,
    card: null,
    blurred_photo_url: BLUR,
    ...overrides,
  };
}

function shown(overrides: Partial<LikeCard> = {}): LikeCard {
  return {
    handle: "b".repeat(32),
    is_super: false,
    blurred_photo_url: null,
    card: {
      id: "u2",
      first_name: "Zeenat",
      age: 24,
      username: "zeenat_k",
      city: "Phagwara",
      hometown: null,
      distance_km: 3,
      intent_ids: [],
      bio_line: "",
      main_photo_url: "https://cdn.test/p/u2.jpg",
      shows_badge: false,
      is_online: false,
      is_new: false,
    },
    ...overrides,
  };
}

function routes(likes: LikeCard[], overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/likes": () => json(200, { items: likes, next_cursor: null }),
    "GET /v1/likes/count": () => json(200, { count: likes.length }),
    "GET /v1/prices": () => json(200, { liked_you_reveal: 3, super_like: 5 }),
    "GET /v1/wallet": () => json(200, { balance: 10 }),
    ...overrides,
  });
}

function renderLikes(gender: "male" | "female") {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  client.setQueryData(queryKeys.me(), { id: "u1", gender });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <LikedYouScreen />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const grid = () => screen.findByRole("list");

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords() {
        return [];
      }
    },
  );
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("Liked you (T-6.7)", () => {
  it("shows a man the server's blur, never a CSS one, and the price from /prices", async () => {
    routes([hidden()]);
    renderLikes("male");

    const tile = within(await grid()).getByRole("listitem");
    const picture = within(tile).getByRole("img", { name: t("likes.someone") });
    expect(picture).toHaveAttribute("src", BLUR);
    expect(picture.className).not.toMatch(/blur/);
    expect(
      await within(tile).findByRole("button", {
        name: t("likes.reveal", { price: creditsText(3) }),
      }),
    ).toBeInTheDocument();
    expect(within(tile).queryByText("Zeenat")).toBeNull();
  });

  it("reveals one, and the tile shows who it was", async () => {
    let revealed = false;
    fakeApi({
      "GET /v1/likes": () =>
        json(200, {
          items: [revealed ? shown() : hidden()],
          next_cursor: null,
        }),
      "GET /v1/likes/count": () => json(200, { count: 1 }),
      "GET /v1/prices": () => json(200, { liked_you_reveal: 3 }),
      "GET /v1/wallet": () => json(200, { balance: 10 }),
      [`POST /v1/likes/${"a".repeat(32)}/reveal`]: (call) => {
        // The price this screen showed, exactly (P-56).
        expect(call.body).toEqual({ shown_price: 3 });
        revealed = true;
        return json(200, shown().card);
      },
    });
    renderLikes("male");

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("likes.reveal", { price: creditsText(3) }),
      }),
    );

    expect(
      await screen.findByText(t("likes.nameAge", { name: "Zeenat", age: 24 })),
    ).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/people/u2");
  });

  it("says the new price when it changed, and charges nothing", async () => {
    fakeApi({
      "GET /v1/likes": () =>
        json(200, { items: [hidden()], next_cursor: null }),
      "GET /v1/likes/count": () => json(200, { count: 1 }),
      "GET /v1/prices": () => json(200, { liked_you_reveal: 3 }),
      "GET /v1/wallet": () => json(200, { balance: 10 }),
      [`POST /v1/likes/${"a".repeat(32)}/reveal`]: () =>
        envelope(409, "PRICE_CHANGED", { price: 4 }),
    });
    renderLikes("male");

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("likes.reveal", { price: creditsText(3) }),
      }),
    );

    expect(
      await screen.findByText(
        t("likes.priceChanged", { velas: creditsText(4) }),
      ),
    ).toBeInTheDocument();
  });

  it("opens the store sheet when he can't afford it", async () => {
    fakeApi({
      "GET /v1/likes": () =>
        json(200, { items: [hidden()], next_cursor: null }),
      "GET /v1/likes/count": () => json(200, { count: 1 }),
      "GET /v1/prices": () => json(200, { liked_you_reveal: 3 }),
      "GET /v1/wallet": () => json(200, { balance: 0 }),
      [`POST /v1/likes/${"a".repeat(32)}/reveal`]: () =>
        envelope(402, "INSUFFICIENT_CREDITS"),
    });
    renderLikes("male");

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("likes.reveal", { price: creditsText(3) }),
      }),
    );

    await waitFor(() => expect(useStoreSheet.getState().open).toBe(true));
    expect(screen.queryByText(t("likes.revealFailed"))).toBeNull();
  });

  it("shows a woman everyone, with no reveal and no prices asked", async () => {
    const api = routes([shown({ is_super: true })]);
    renderLikes("female");

    const tile = within(await grid()).getByRole("listitem");
    expect(
      within(tile).getByText(t("likes.nameAge", { name: "Zeenat", age: 24 })),
    ).toBeInTheDocument();
    expect(
      within(tile).getByRole("img", { name: t("likes.superLike") }),
    ).toBeInTheDocument();
    expect(within(tile).queryByRole("button")).toBeNull();
    expect(api.sent()).not.toContain("GET /v1/prices");
  });

  it("shows the count in the header", async () => {
    routes([hidden(), hidden({ handle: "c".repeat(32) })]);
    renderLikes("male");

    expect(
      await screen.findByRole("img", { name: t("likes.count", { count: 2 }) }),
    ).toHaveTextContent("2");
  });

  it("says when nobody has yet", async () => {
    routes([]);
    renderLikes("male");

    expect(await screen.findByText(t("likes.empty"))).toBeInTheDocument();
  });

  it("says when the list failed, and tries again", async () => {
    let fail = true;
    routes([], {
      "GET /v1/likes": () =>
        fail
          ? envelope(500, "INTERNAL")
          : json(200, { items: [hidden()], next_cursor: null }),
    });
    renderLikes("male");

    // The toast's own region is an alert too: the error is the one saying it.
    const message = await screen.findByText(t("likes.failed"));
    const alert = message.closest<HTMLElement>('[role="alert"]');
    if (!alert) throw new Error("the error isn't announced as an alert");
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(within(await grid()).getAllByRole("listitem")).toHaveLength(1);
  });
});
