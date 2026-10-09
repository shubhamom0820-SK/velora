import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import YouPage from "@/app/(app)/you/page";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { resetSession, useSession } from "@/store/session";

type Gender = "female" | "male";

function me(gender: Gender, overrides: Record<string, unknown> = {}) {
  return {
    id: "u1",
    role: "user",
    status: "active",
    onboarding_step: "done",
    gender,
    age: 27,
    is_verified: gender === "female",
    has_pin: true,
    referral_code: null,
    balance: gender === "male" ? 12 : 0,
    profile: {
      first_name: "Priya",
      username: "priya_k",
      about: "Reads on trains, cooks on Sundays, walks everywhere she can.",
      hometown: "Jalandhar",
      city: "Phagwara",
      seeking: gender === "female" ? "men" : "women",
      intent_ids: [1],
      interest_ids: [1, 2, 3, 4, 5],
      is_hidden: false,
      hide_age: false,
      hide_distance: false,
      show_kudos: true,
      show_gifts: true,
      public_link: false,
      location: "fresh",
    },
    ...overrides,
  };
}

function card(
  id: string,
  name: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id,
    first_name: name,
    username: name.toLowerCase(),
    main_photo_url: null,
    shows_badge: false,
    is_online: false,
    deleted: false,
    ...overrides,
  };
}

function knot(id: string, other: ReturnType<typeof card>) {
  return {
    id,
    origin: "match",
    status: "knotted",
    expires_at: null,
    knotted_at: "2026-10-08T10:00:00Z",
    i_tied: true,
    unread: 0,
    last_message: null,
    last_message_at: null,
    other,
  };
}

const EMPTY = { items: [], next_cursor: null };
const page = (items: unknown[]) => json(200, { items, next_cursor: null });

/** Every list the tab asks for, empty, unless a test says otherwise. */
function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/users/u1": () =>
      json(200, { main_photo_url: null, shows_badge: true }),
    "GET /v1/me/kudos": () => json(200, []),
    "GET /v1/threads": () => json(200, EMPTY),
    "GET /v1/blocks": () => json(200, EMPTY),
    "GET /v1/reports": () => json(200, EMPTY),
    "GET /v1/threads/cleared": () => json(200, EMPTY),
    "GET /v1/gifts": () =>
      json(200, {
        gifts: [],
        free_sends_left: null,
        free_sends_reset_at: null,
      }),
    "GET /v1/me/gifts": () => json(200, EMPTY),
    ...overrides,
  });
}

function renderYou(gender: Gender = "female", overrides = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), me(gender, overrides));
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <YouPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

function section(name: string): HTMLElement {
  return screen.getByRole("region", { name });
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  resetSession();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the You tab (T-9.8)", () => {
  it("shows who you are, with the badge as others see it", async () => {
    routes();
    renderYou();

    expect(
      screen.getByRole("heading", { level: 1, name: t("you.title") }),
    ).toBeInTheDocument();
    expect(screen.getByText("Priya, 27")).toBeInTheDocument();
    expect(screen.getByText("@priya_k")).toBeInTheDocument();
    expect(screen.getByText(en.intents["1"])).toBeInTheDocument();
    expect(await screen.findByText(t("ui.selfieMatched"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t("you.edit") })).toHaveAttribute(
      "href",
      "/you/edit",
    );
    expect(screen.getByRole("link", { name: t("you.photos") })).toHaveAttribute(
      "href",
      "/you/photos",
    );
  });

  it("says the main photo hasn't matched yet, never the badge from is_verified alone (D-910)", async () => {
    routes({
      "GET /v1/users/u1": () =>
        json(200, { main_photo_url: null, shows_badge: false }),
    });
    renderYou();

    expect(
      await screen.findByText(t("you.selfieMainNotYet")),
    ).toBeInTheDocument();
    expect(screen.queryByText(t("ui.selfieMatched"))).toBeNull();
  });

  it("says a man who skipped the selfie has no check yet", async () => {
    routes({
      "GET /v1/users/u1": () =>
        json(200, { main_photo_url: null, shows_badge: false }),
    });
    renderYou("male");

    expect(await screen.findByText(t("you.selfieNone"))).toBeInTheDocument();
  });

  it("says each list is empty on its own", async () => {
    routes();
    renderYou();

    for (const line of [
      t("you.kudos.empty"),
      t("you.knots.empty"),
      t("you.blocked.empty"),
      t("you.reports.empty"),
      t("you.cleared.empty"),
    ]) {
      expect(await screen.findByText(line)).toBeInTheDocument();
    }
  });

  it("says which list didn't load, and tries that one again", async () => {
    let fail = true;
    const failing: Route = () =>
      fail ? envelope(500, "INTERNAL") : json(200, EMPTY);
    routes({
      "GET /v1/me/kudos": () =>
        fail ? envelope(500, "INTERNAL") : json(200, []),
      "GET /v1/threads": failing,
      "GET /v1/blocks": failing,
      "GET /v1/reports": failing,
      "GET /v1/threads/cleared": failing,
    });
    renderYou();

    for (const title of [
      t("you.kudos.failed"),
      t("you.knots.failed"),
      t("you.blocked.failed"),
      t("you.reports.failed"),
    ]) {
      expect(await screen.findByText(title)).toBeInTheDocument();
    }
    const cleared = await screen.findByText(t("you.cleared.failed"));
    const alert = cleared.closest<HTMLElement>('[role="alert"]');
    if (!alert) throw new Error("the error isn't announced as an alert");
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(await screen.findByText(t("you.cleared.empty"))).toBeInTheDocument();
  });

  it("shows each section loading while its list is on its way", () => {
    const never: Route = () => new Promise<Response>(() => undefined);
    routes({
      "GET /v1/me/kudos": never,
      "GET /v1/threads": never,
      "GET /v1/blocks": never,
      "GET /v1/reports": never,
      "GET /v1/threads/cleared": never,
    });
    renderYou("male");

    for (const name of [
      t("you.knots.title"),
      t("you.blocked.title"),
      t("you.reports.title"),
      t("you.cleared.title"),
    ]) {
      expect(section(name).querySelector('[aria-busy="true"]')).not.toBeNull();
    }
  });

  it("counts the kudos you were given, by kind", async () => {
    routes({
      "GET /v1/me/kudos": () =>
        json(200, [{ kind: "great_conversation", count: 3 }]),
    });
    renderYou();

    expect(
      await screen.findByText(
        t("you.kudos.count", {
          label: t("profile.kudosKind.great_conversation"),
          count: 3,
        }),
      ),
    ).toBeInTheDocument();
  });

  it("lists your Knots, each opening its chat, and asks before untying", async () => {
    const api = routes({
      "GET /v1/threads": (call) =>
        call.query.get("tier") === "knots"
          ? page([knot("k1", card("m1", "Arjun"))])
          : json(200, EMPTY),
      "DELETE /v1/threads/k1/knot": () =>
        json(200, knot("k1", card("m1", "Arjun"))),
    });
    renderYou();

    const knots = section(t("you.knots.title"));
    expect(
      await within(knots).findByRole("link", { name: /Arjun/ }),
    ).toHaveAttribute("href", "/chats/k1");
    await userEvent.click(
      within(knots).getByRole("button", {
        name: t("you.knots.untieName", { name: "Arjun" }),
      }),
    );
    const sheet = await screen.findByRole("dialog", {
      name: t("you.knots.untieTitle", { name: "Arjun" }),
    });
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("you.knots.untieCancel") }),
    );
    expect(api.sent()).not.toContain("DELETE /v1/threads/k1/knot");

    await userEvent.click(
      within(knots).getByRole("button", {
        name: t("you.knots.untieName", { name: "Arjun" }),
      }),
    );
    await userEvent.click(
      within(
        await screen.findByRole("dialog", {
          name: t("you.knots.untieTitle", { name: "Arjun" }),
        }),
      ).getByRole("button", { name: t("you.knots.untieConfirm") }),
    );

    await waitFor(() =>
      expect(api.sent()).toContain("DELETE /v1/threads/k1/knot"),
    );
    expect(await screen.findByText(t("you.knots.untied"))).toBeInTheDocument();
  });

  it("unblocks from the blocked list (P-762)", async () => {
    let blocked = true;
    const api = routes({
      "GET /v1/blocks": () =>
        blocked
          ? page([
              {
                user: card("b1", "Kabir"),
                blocked_at: "2026-10-09T10:00:00Z",
              },
            ])
          : json(200, EMPTY),
      "DELETE /v1/blocks/b1": () => {
        blocked = false;
        return new Response(null, { status: 204 });
      },
    });
    renderYou();

    const list = section(t("you.blocked.title"));
    await userEvent.click(
      await within(list).findByRole("button", {
        name: t("you.blocked.unblockName", { name: "Kabir" }),
      }),
    );

    expect(
      await screen.findByText(t("you.blocked.unblocked", { name: "Kabir" })),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("DELETE /v1/blocks/b1");
    expect(
      await within(list).findByText(t("you.blocked.empty")),
    ).toBeInTheDocument();
    // Their profile is hidden while blocked: the row opens nothing.
    expect(within(list).queryByRole("link")).toBeNull();
  });

  it("says when an unblock failed", async () => {
    routes({
      "GET /v1/blocks": () =>
        page([
          { user: card("b1", "Kabir"), blocked_at: "2026-10-09T10:00:00Z" },
        ]),
      "DELETE /v1/blocks/b1": () => envelope(429, "RATE_LIMITED"),
    });
    renderYou();

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("you.blocked.unblockName", { name: "Kabir" }),
      }),
    );

    expect(
      await screen.findByText(
        t("you.blocked.unblockFailed", { name: "Kabir" }),
      ),
    ).toBeInTheDocument();
  });

  it("lists your reports with why and when, never a status or a time to an answer (D-911)", async () => {
    routes({
      "GET /v1/reports": () =>
        page([
          {
            id: "r1",
            reason: "harass",
            created_at: "2026-10-09T10:00:00Z",
            reported: card("x1", "Rohit"),
          },
        ]),
    });
    renderYou();

    const reports = section(t("you.reports.title"));
    expect(await within(reports).findByText("Rohit")).toBeInTheDocument();
    expect(
      within(reports).getByText(new RegExp(t("profile.reason.harass"))),
    ).toBeInTheDocument();
    expect(reports).not.toHaveTextContent(/24 hours|resolved|actioned|banned/i);
  });

  it("restores a cleared chat, one at a time (D-912)", async () => {
    let cleared = true;
    const api = routes({
      "GET /v1/threads/cleared": () =>
        cleared
          ? page([{ ...knot("t1", card("m2", "Dev")), status: "expired" }])
          : json(200, EMPTY),
      "DELETE /v1/threads/t1/clear": () => {
        cleared = false;
        return new Response(null, { status: 204 });
      },
    });
    renderYou();

    const list = section(t("you.cleared.title"));
    await userEvent.click(
      await within(list).findByRole("button", {
        name: t("you.cleared.restoreName", { name: "Dev" }),
      }),
    );

    expect(
      await screen.findByText(t("you.cleared.restored")),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("DELETE /v1/threads/t1/clear");
    expect(
      await within(list).findByText(t("you.cleared.empty")),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /restore all/i })).toBeNull();
  });

  it("links the settings rows, your album's requests included (T-8.8, D-790)", async () => {
    routes();
    renderYou("male");

    for (const [name, href] of [
      [t("you.account"), "/you/settings"],
      [t("notifications.you.list"), "/notifications"],
      [t("notifications.you.settings"), "/you/notifications"],
      [t("albumRequests.title"), "/you/album-requests"],
    ] as const) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(
      screen.getByRole("button", { name: t("session.signOut") }),
    ).toBeInTheDocument();
    // Referrals are paused (D-840): no invite or share card.
    expect(document.body).not.toHaveTextContent(
      /invite|referral|refer a friend/i,
    );
  });

  it("locks the app at once with Lock now", async () => {
    routes();
    useSession.getState().signIn("token");
    renderYou();

    await userEvent.click(
      screen.getByRole("button", { name: t("you.lockNow") }),
    );

    expect(useSession.getState().locked).toBe(true);
  });

  it("offers no Lock now without a PIN", () => {
    routes();
    renderYou("male", { has_pin: false });

    expect(screen.queryByRole("button", { name: t("you.lockNow") })).toBeNull();
  });

  it("shows her gifts to her alone (T-8.10)", async () => {
    const api = routes();
    renderYou("male");

    expect(screen.queryByText(t("gifts.yours"))).toBeNull();
    await waitFor(() => expect(api.sent()).toContain("GET /v1/blocks"));
    expect(api.sent()).not.toContain("GET /v1/me/gifts");
  });

  it("says when you couldn't be loaded, and tries again", async () => {
    let fail = true;
    routes({
      "GET /v1/me": () =>
        fail ? envelope(500, "INTERNAL") : json(200, me("female")),
    });
    useSession.getState().signIn("token");
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <YouPage />
        </ToastProvider>
      </QueryClientProvider>,
    );

    const message = await screen.findByText(t("you.summaryFailed"));
    fail = false;
    const alert = message.closest<HTMLElement>('[role="alert"]');
    if (!alert) throw new Error("the error isn't announced as an alert");
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );

    expect(await screen.findByText("Priya, 27")).toBeInTheDocument();
  });
});
