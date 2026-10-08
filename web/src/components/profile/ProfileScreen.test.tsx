import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import type { PublicProfile } from "@/lib/queries/profiles";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { ProfileScreen } from "./ProfileScreen";

function her(overrides: Partial<PublicProfile> = {}): PublicProfile {
  return {
    id: "u2",
    first_name: "Simran",
    age: 24,
    username: "simran.k",
    city: "Phagwara",
    hometown: "Jalandhar",
    distance_km: 3,
    intent_ids: [1],
    bio_line: "Morning runs",
    main_photo_url: "https://cdn.test/p/1.jpg",
    shows_badge: true,
    is_online: true,
    is_new: false,
    about: "Morning runs by the canal, evening chai.",
    photo_urls: ["https://cdn.test/p/1.jpg", "https://cdn.test/p/2.jpg"],
    interest_ids: [3],
    kudos: {
      great_conversation: 2,
      genuinely_funny: 0,
      easy_to_talk_to: 1,
      really_thoughtful: 0,
    },
    album_photo_count: 2,
    match_id: null,
    thread: null,
    can_gift: false,
    ...overrides,
  };
}

const CATALOGUE = {
  gifts: [
    { id: "coffee", label: "Coffee", asset: "☕", credits: 5 },
    { id: "rose", label: "Rose", asset: "🌹", credits: 10 },
  ],
  free_sends_left: 15,
  free_sends_reset_at: "2026-10-11T18:30:00Z",
};

function routes(profile: Route, overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/users/u2": profile,
    // The album row asks for its state (T-8.8): never asked, by default.
    "GET /v1/users/u2/album": () => json(200, { status: null, photos: [] }),
    "GET /v1/prices": () => json(200, { album_request: 1 }),
    "GET /v1/users/u2/gifts": () => json(200, { counts: [] }),
    "GET /v1/gifts": () => json(200, CATALOGUE),
    ...overrides,
  });
}

const THREAD = {
  id: "t1",
  status: "active",
  expires_at: null,
} as const;

function renderProfile(meId = "u1", showGifts = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), {
    id: meId,
    gender: "male",
    profile: { show_gifts: showGifts },
  });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ProfileScreen id="u2" />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const name = () =>
  screen.findByRole("heading", {
    level: 1,
    name: t("profile.nameAge", { name: "Simran", age: 24 }),
  });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the profile (T-6.8)", () => {
  it("shows the gallery, the facts, the chips, the kudos and the album's count", async () => {
    routes(() => json(200, her()));
    renderProfile();

    await name();
    expect(
      screen.getByRole("img", { name: t("profile.photo", { n: 2, total: 2 }) }),
    ).toHaveAttribute("src", "https://cdn.test/p/2.jpg");
    expect(
      screen.getByText("Phagwara · 3 km · from Jalandhar"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: t("ui.selfieMatched") }),
    ).toBeInTheDocument();
    expect(screen.getByText(t("profile.selfieNote"))).toBeInTheDocument();
    expect(screen.getByText(t("profile.online"))).toBeInTheDocument();
    expect(screen.getByText("Something serious")).toBeInTheDocument();
    expect(screen.getByText("Indie music")).toBeInTheDocument();
    expect(
      screen.getByText(t("profile.kudosKind.great_conversation")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("profile.albumOther", { count: 2 })),
    ).toBeInTheDocument();
  });

  it("shows no badge or note where D-393's rule doesn't hold, and no kudos when hidden", async () => {
    routes(() =>
      json(200, her({ shows_badge: false, kudos: null, album_photo_count: 0 })),
    );
    renderProfile();

    await name();
    expect(
      screen.queryByRole("img", { name: t("ui.selfieMatched") }),
    ).toBeNull();
    expect(screen.queryByText(t("profile.selfieNote"))).toBeNull();
    expect(screen.queryByText(t("profile.kudos"))).toBeNull();
    expect(screen.queryByText(t("profile.album"))).toBeNull();
  });

  it("shows a silhouette with no photo, and no age when it is hidden", async () => {
    routes(() =>
      json(200, her({ photo_urls: [], main_photo_url: null, age: null })),
    );
    renderProfile();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Simran" }),
    ).toBeInTheDocument();
    expect(screen.getByText(t("profile.noPhoto"))).toBeInTheDocument();
  });

  it("renders their text as text, never as markup", async () => {
    const about = '<img src="x" onerror="window.__pwned=1">';
    routes(() => json(200, her({ about })));
    const { container } = renderProfile();

    await name();
    expect(screen.getByText(about)).toBeInTheDocument();
    expect(container.querySelector('img[src="x"]')).toBeNull();
  });

  it("likes them, and says so when it matched", async () => {
    const api = routes(() => json(200, her()), {
      "POST /v1/swipes": () =>
        json(200, { matched: true, match_id: "m1", swipes_left: 49 }),
    });
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", { name: t("profile.like") }),
    );

    expect(
      await screen.findByRole("button", { name: t("profile.liked") }),
    ).toBeDisabled();
    expect(await screen.findByText(t("profile.matched"))).toBeInTheDocument();
    expect(api.calls.find((c) => c.method === "POST")?.body).toEqual({
      target_id: "u2",
      dir: "like",
      shown_price: 0,
    });
  });

  it("reads a like already given, here or in the deck, as given", async () => {
    routes(() => json(200, her()), {
      "POST /v1/swipes": () => envelope(409, "ALREADY_EXISTS"),
    });
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", { name: t("profile.like") }),
    );
    expect(
      await screen.findByRole("button", { name: t("profile.liked") }),
    ).toBeDisabled();
  });

  it("says why the API refused a like", async () => {
    routes(() => json(200, her()), {
      "POST /v1/swipes": () => envelope(404, "NOT_FOUND"),
    });
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", { name: t("profile.like") }),
    );

    expect(
      await screen.findByText(t("profile.likeRefused")),
    ).toBeInTheDocument();
  });

  it("shows your own without the like bar", async () => {
    routes(() => json(200, her()));
    renderProfile("u2");

    await name();
    expect(screen.getByText(t("profile.yours"))).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("profile.like") }),
    ).toBeNull();
  });

  it("shows your own album's count as others see it, and asks nothing about it", async () => {
    const api = routes(() => json(200, her()));
    renderProfile("u2");

    await name();
    expect(
      screen.getByText(t("profile.albumOther", { count: 2 })),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: new RegExp(t("profile.albumAsk", { price: "" }).trim()),
      }),
    ).toBeNull();
    // Her gifts row asks for its counts (T-8.10); nothing about the album.
    expect(api.sent().filter((sent) => !sent.includes("/gifts"))).toEqual([
      "GET /v1/users/u2",
    ]);
  });

  it("offers a gift where the API says one is taken, in its sheet", async () => {
    routes(() => json(200, her({ can_gift: true })));
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", { name: t("gifts.give") }),
    );

    const sheet = await screen.findByRole("dialog", {
      name: t("gifts.title", { name: "Simran" }),
    });
    expect(
      await within(sheet).findByRole("button", { name: "Rose, Free" }),
    ).toBeInTheDocument();
  });

  it("offers no gift where the API says none is taken (D-780)", async () => {
    routes(() => json(200, her({ can_gift: false })));
    renderProfile();

    await name();
    expect(
      screen.getByRole("button", { name: t("profile.like") }),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: t("gifts.give") })).toBeNull();
  });

  it("shows how many of each gift she received, never from whom or a price", async () => {
    routes(() => json(200, her()), {
      "GET /v1/users/u2/gifts": () =>
        json(200, { counts: [{ gift_id: "rose", count: 3 }] }),
    });
    renderProfile();

    const heading = await screen.findByRole("heading", {
      level: 2,
      name: t("gifts.received"),
    });
    const row = heading.closest("section");
    if (!row) throw new Error("the gifts row has no section");
    expect(within(row).getByText("3")).toBeInTheDocument();
    expect(within(row).getByText("Rose")).toBeInTheDocument();
    expect(within(row).queryByText(/Vela/)).toBeNull();
    expect(screen.queryByText(t("gifts.onlyYou"))).toBeNull();
  });

  it("shows no gifts row when she received none, or hides them", async () => {
    routes(() => json(200, her()));
    renderProfile();

    await name();
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { level: 2, name: t("gifts.received") }),
      ).toBeNull(),
    );
  });

  it("shows her own gifts to her with a note while they are hidden", async () => {
    routes(() => json(200, her()), {
      "GET /v1/users/u2/gifts": () =>
        json(200, { counts: [{ gift_id: "coffee", count: 1 }] }),
    });
    renderProfile("u2", false);

    expect(await screen.findByText(t("gifts.onlyYou"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("gifts.give") })).toBeNull();
  });

  it("shares the profile's /@username link", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal("navigator", {
      ...navigator,
      share: undefined,
      clipboard: { writeText },
    });
    routes(() => json(200, her()));
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", { name: t("profile.more") }),
    );
    await userEvent.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: t("profile.share"),
      }),
    );

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(
        `${window.location.origin}/@simran.k`,
      ),
    );
    expect(await screen.findByText(t("profile.copied"))).toBeInTheDocument();
  });

  it("says a profile it may not see isn't available, as one NOT_FOUND", async () => {
    routes(() => envelope(404, "NOT_FOUND"));
    renderProfile();

    expect(await screen.findByText(t("profile.notFound"))).toBeInTheDocument();
  });

  it("says when it failed, and tries again", async () => {
    let fail = true;
    routes(() => (fail ? envelope(500, "INTERNAL") : json(200, her())));
    renderProfile();

    const message = await screen.findByText(t("profile.failed"));
    fail = false;
    const alert = message.closest<HTMLElement>('[role="alert"]');
    if (!alert) throw new Error("the error isn't announced as an alert");
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(await name()).toBeInTheDocument();
  });
});

describe("the kudos prompt (T-8.8, D-790)", () => {
  const ask = () =>
    screen.queryByRole("region", {
      name: t("profile.kudosAsk", { name: "Simran" }),
    });

  it("shows when their Thread says kudos can be given", async () => {
    routes(() => json(200, her({ thread: { ...THREAD, kudos: "can_give" } })));
    renderProfile();

    await name();
    const prompt = ask();
    expect(prompt).not.toBeNull();
    expect(
      within(prompt as HTMLElement)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual([
      t("profile.kudosKind.great_conversation"),
      t("profile.kudosKind.genuinely_funny"),
      t("profile.kudosKind.easy_to_talk_to"),
      t("profile.kudosKind.really_thoughtful"),
    ]);
  });

  it.each(["too_early", "given"] as const)(
    "never shows when it says %s, so a tap is never refused (P-580)",
    async (kudos) => {
      routes(() => json(200, her({ thread: { ...THREAD, kudos } })));
      renderProfile();

      await name();
      expect(ask()).toBeNull();
    },
  );

  it("never shows with no Thread, nor on your own profile", async () => {
    routes(() => json(200, her({ thread: null })));
    const first = renderProfile();
    await name();
    expect(ask()).toBeNull();
    first.unmount();

    routes(() => json(200, her({ thread: { ...THREAD, kudos: "can_give" } })));
    renderProfile("u2");
    await name();
    expect(ask()).toBeNull();
  });

  it("gives the kind tapped, and goes once the profile says given", async () => {
    let given = false;
    routes(
      () =>
        json(
          200,
          her({ thread: { ...THREAD, kudos: given ? "given" : "can_give" } }),
        ),
      {
        "POST /v1/kudos": (call) => {
          expect(call.body).toEqual({
            to_id: "u2",
            kind: "easy_to_talk_to",
          });
          given = true;
          return json(201, {
            to_id: "u2",
            kind: "easy_to_talk_to",
            created_at: "2026-10-09T10:00:00Z",
          });
        },
      },
    );
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", {
        name: t("profile.kudosKind.easy_to_talk_to"),
      }),
    );

    expect(await screen.findByText(t("profile.kudosSent"))).toBeInTheDocument();
    await waitFor(() => expect(ask()).toBeNull());
  });

  it("takes kudos already given as given, never as an error", async () => {
    let given = false;
    routes(
      () =>
        json(
          200,
          her({ thread: { ...THREAD, kudos: given ? "given" : "can_give" } }),
        ),
      {
        "POST /v1/kudos": () => {
          given = true;
          return envelope(409, "ALREADY_EXISTS");
        },
      },
    );
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", {
        name: t("profile.kudosKind.great_conversation"),
      }),
    );

    await waitFor(() => expect(ask()).toBeNull());
    expect(screen.queryByText(t("profile.kudosFailed"))).toBeNull();
    expect(screen.queryByText(/ALREADY_EXISTS/)).toBeNull();
  });

  it("says too early in words, and the prompt goes when the profile agrees", async () => {
    let early = false;
    routes(
      () =>
        json(
          200,
          her({
            thread: { ...THREAD, kudos: early ? "too_early" : "can_give" },
          }),
        ),
      {
        "POST /v1/kudos": () => {
          early = true;
          return envelope(422, "NOT_ALLOWED", { why: "too_early" });
        },
      },
    );
    renderProfile();

    await name();
    await userEvent.click(
      screen.getByRole("button", {
        name: t("profile.kudosKind.really_thoughtful"),
      }),
    );

    expect(
      await screen.findByText(t("profile.kudosTooEarly")),
    ).toBeInTheDocument();
    await waitFor(() => expect(ask()).toBeNull());
  });
});
