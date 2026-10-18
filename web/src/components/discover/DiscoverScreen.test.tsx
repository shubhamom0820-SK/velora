import { Globals } from "@react-spring/web";
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import type { Card } from "@/lib/queries/discover";
import { queryKeys } from "@/lib/queries/keys";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import {
  envelope,
  fakeApi,
  json,
  type Call,
  type Route,
} from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { DiscoverScreen } from "./DiscoverScreen";

// The action row names whoever is on top (T-9.11): "Like Priya".
const LIKE = /^Like \S+$/;
const PASS = /^Pass on \S+$/;
const SUPER = /^Super Like \S+$/;
const superPriced = (velas: string) =>
  new RegExp(`^Super Like \\S+, ${velas}$`);

const nav = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  search: "",
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: nav.push,
    replace: nav.replace,
    prefetch: vi.fn(),
  }),
  usePathname: () => "/discover",
  useSearchParams: () => new URLSearchParams(nav.search),
}));

/**
 * `/prices` with prices no screen has ever said: a number written into the
 * code (5) can't pass for one read from here (P-56).
 */
const PRICES = { super_like: 7, thread_open: 9, thread_reopen: 2 };

let ids = 0;
function card(overrides: Partial<Card> = {}): Card {
  ids += 1;
  return {
    id: `00000000-0000-4000-8000-${String(ids).padStart(12, "0")}`,
    first_name: `Person${ids}`,
    age: 24,
    username: `person${ids}`,
    city: "Phagwara",
    hometown: "Jalandhar",
    distance_km: 3,
    intent_ids: [1],
    bio_line: "Chai, cricket and long walks.",
    main_photo_url: "https://cdn.test/p.jpg",
    shows_badge: false,
    is_online: false,
    is_new: false,
    ...overrides,
  };
}

function page(
  items: Card[],
  {
    next = null,
    left = 50,
  }: { next?: string | null; left?: number | null } = {},
) {
  return json(200, { items, next_cursor: next, swipes_left: left });
}

function swipeOk(overrides: Record<string, unknown> = {}): Route {
  return () =>
    json(200, {
      matched: false,
      match_id: null,
      swipes_left: 49,
      ...overrides,
    });
}

let client: QueryClient;

function renderAs(gender: "male" | "female") {
  client.setQueryData(queryKeys.me(), {
    id: "me",
    gender,
    profile: { first_name: "Sam" },
  });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <DiscoverScreen />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The card on top: the one a swipe takes. */
const topName = () =>
  within(screen.getByTestId("top-card"))
    .getByRole("article")
    .getAttribute("aria-label");

/** The toast region stays mounted (ToastProvider); empty means no toast. */
const noToast = () =>
  screen.getAllByRole("alert").every((region) => region.textContent === "");

const swipes = (calls: Call[]) =>
  calls.filter((c) => c.method === "POST" && c.path === "/v1/swipes");

const reads = (calls: Call[], path: string) =>
  calls.filter((c) => c.method === "GET" && c.path === path);

beforeAll(() => {
  // Springs land at once: a flight's end is what the tests wait on.
  Globals.assign({ skipAnimation: true });
});

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = makeQueryClient();
  nav.push.mockReset();
  nav.replace.mockReset();
  nav.search = "";
  ids = 0;
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the card (T-6.5, 08-DESIGN §8)", () => {
  it("shows the name and age, the place, online, the intents and the bio, and the tick where the badge holds", async () => {
    fakeApi({
      "GET /v1/discover": () =>
        page([
          card({ first_name: "Simran", shows_badge: true, is_online: true }),
        ]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    const top = await screen.findByRole("article", { name: "Simran" });
    expect(
      within(top).getByRole("link", {
        name: t("discover.card.openProfile", { name: "Simran" }),
      }),
    ).toHaveAttribute("href", "/people/00000000-0000-4000-8000-000000000001");
    expect(within(top).getByText("Simran, 24")).toBeInTheDocument();
    expect(within(top).getByText("Phagwara · 3 km")).toBeInTheDocument();
    expect(
      within(top).getByText(t("discover.card.online")),
    ).toBeInTheDocument();
    expect(within(top).getByText("Something serious")).toBeInTheDocument();
    expect(
      within(top).getByText("Chai, cricket and long walks."),
    ).toBeInTheDocument();
    expect(
      within(top).getByRole("img", { name: t("ui.selfieMatched") }),
    ).toBeInTheDocument();
  });

  it("with no photo: the silhouette and its words, and never the tick (D-392, D-393)", async () => {
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ main_photo_url: null, shows_badge: true })]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    const top = await screen.findByRole("article");
    expect(
      within(top).getByText(t("discover.card.noPhoto")),
    ).toBeInTheDocument();
    expect(
      within(top).queryByRole("img", { name: t("ui.selfieMatched") }),
    ).toBeNull();
  });

  it("leaves out what is hidden or unearned: no age, no distance, no tick", async () => {
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "Asha", age: null, distance_km: null })]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    const top = await screen.findByRole("article", { name: "Asha" });
    expect(within(top).getByRole("heading")).toHaveTextContent(/^Asha$/);
    expect(within(top).getByText("Phagwara")).toBeInTheDocument();
    // A photo, but the badge's rule doesn't hold (D-393): no tick.
    expect(
      within(top).queryByRole("img", { name: t("ui.selfieMatched") }),
    ).toBeNull();
  });

  it("draws three cards at most, however many are left", async () => {
    fakeApi({
      "GET /v1/discover": () => page(Array.from({ length: 8 }, () => card())),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    await screen.findByTestId("top-card");
    expect(screen.getAllByRole("article", { hidden: true })).toHaveLength(3);
  });
});

describe("the price a man is shown is the price he sends (P-56, D-600)", () => {
  it("shows Super's price from /prices as a number, and sends exactly it", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");

    const superLike = await screen.findByRole("button", {
      name: superPriced("7 Velas"),
    });
    await waitFor(() => expect(superLike).toBeEnabled());
    expect(superLike).toHaveTextContent(/^7$/);
    await userEvent.click(superLike);

    await waitFor(() => expect(swipes(api.calls)).toHaveLength(1));
    expect(swipes(api.calls)[0]?.body).toEqual({
      target_id: "00000000-0000-4000-8000-000000000001",
      dir: "super",
      shown_price: 7,
    });
  });

  it("keeps his Super Like off until the price has loaded", async () => {
    let answer: (response: Response) => void = () => {};
    fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => new Promise<Response>((r) => (answer = r)),
    });
    renderAs("male");

    await screen.findByTestId("top-card");
    expect(screen.getByRole("button", { name: SUPER })).toBeDisabled();
    await act(async () => answer(json(200, PRICES)));
    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: superPriced("7 Velas"),
        }),
      ).toBeEnabled(),
    );
  });

  it("hides Super when /prices has switched it off", async () => {
    fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, { thread_open: 9 }),
    });
    renderAs("male");

    await screen.findByTestId("top-card");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /super like/i })).toBeNull(),
    );
  });

  it("sends 0 with a like or a pass, which cost nothing", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    await userEvent.click(screen.getByRole("button", { name: LIKE }));
    await userEvent.click(screen.getByRole("button", { name: PASS }));

    await waitFor(() => expect(swipes(api.calls)).toHaveLength(2));
    expect(swipes(api.calls).map((c) => c.body)).toEqual([
      expect.objectContaining({ dir: "like", shown_price: 0 }),
      expect.objectContaining({ dir: "pass", shown_price: 0 }),
    ]);
  });

  it("marks a Super Like as spending Velas, and a like not (T-5.5)", async () => {
    fakeApi({
      "GET /v1/discover": () => page([card(), card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    const superLike = await screen.findByRole("button", {
      name: superPriced("7 Velas"),
    });
    await waitFor(() => expect(superLike).toBeEnabled());

    await userEvent.click(superLike);
    await userEvent.click(screen.getByRole("button", { name: LIKE }));

    await waitFor(() =>
      expect(client.getMutationCache().getAll()).toHaveLength(2),
    );
    expect(
      client
        .getMutationCache()
        .getAll()
        .map((m) => m.meta),
    ).toEqual([{ touchesWallet: true }, undefined]);
  });
});

describe("a woman's deck: no price, no count (D-002)", () => {
  it("shows no price anywhere and sends 0 with her Super Like", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()], { left: null }),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk({ swipes_left: null }),
    });
    const { container } = renderAs("female");
    await screen.findByTestId("top-card");

    const superLike = screen.getByRole("button", {
      name: SUPER,
    });
    expect(superLike).toBeEnabled();
    expect(superLike).toHaveTextContent("");
    expect(container).not.toHaveTextContent(/vela/i);
    expect(screen.queryByText(/swipes? left/)).toBeNull();

    await userEvent.click(superLike);
    await waitFor(() => expect(swipes(api.calls)).toHaveLength(1));
    expect(swipes(api.calls)[0]?.body).toEqual(
      expect.objectContaining({ dir: "super", shown_price: 0 }),
    );
  });
});

describe("the optimistic swipe (T-6.5)", () => {
  it("takes the card off before the API answers", async () => {
    let answer: (response: Response) => void = () => {};
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card({ first_name: "Second" })]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": () => new Promise<Response>((r) => (answer = r)),
    });
    renderAs("male");
    await screen.findByRole("article", { name: "First" });

    await userEvent.click(screen.getByRole("button", { name: LIKE }));

    expect(topName()).toBe("Second");
    await act(async () =>
      answer(json(200, { matched: false, match_id: null, swipes_left: 49 })),
    );
    expect(topName()).toBe("Second");
  });

  it.each([
    [
      "a network failure",
      () => Promise.reject(new TypeError("Failed to fetch")),
      t("discover.errors.failed"),
    ],
    ["a 500", () => envelope(500, "INTERNAL"), t("discover.errors.failed")],
  ])("puts the card back with a toast after %s", async (_, route, words) => {
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card({ first_name: "Second" })]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": route as Route,
    });
    renderAs("male");
    await screen.findByRole("article", { name: "First" });

    await userEvent.click(screen.getByRole("button", { name: LIKE }));

    expect(await screen.findByRole("alert")).toHaveTextContent(words);
    await waitFor(() => expect(topName()).toBe("First"));
  });

  it("puts a Super Like back and opens the store when he is out of Velas", async () => {
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card({ first_name: "Second" })]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": () =>
        envelope(402, "INSUFFICIENT_CREDITS", { required: 7, balance: 2 }),
    });
    renderAs("male");
    const superLike = await screen.findByRole("button", {
      name: superPriced("7 Velas"),
    });
    await waitFor(() => expect(superLike).toBeEnabled());

    await userEvent.click(superLike);

    await waitFor(() => expect(useStoreSheet.getState().open).toBe(true));
    await waitFor(() => expect(topName()).toBe("First"));
    expect(noToast()).toBe(true);
  });

  it("puts a Super Like back, says the new price and asks /prices again when it changed (P-56)", async () => {
    let price = 7;
    const api = fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card({ first_name: "Second" })]),
      "GET /v1/prices": () => json(200, { ...PRICES, super_like: price }),
      "POST /v1/swipes": () => {
        price = 8;
        return envelope(409, "PRICE_CHANGED", { price: 8 });
      },
    });
    renderAs("male");
    const superLike = await screen.findByRole("button", {
      name: superPriced("7 Velas"),
    });
    await waitFor(() => expect(superLike).toBeEnabled());

    await userEvent.click(superLike);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("discover.errors.priceChanged", { velas: "8 Velas" }),
    );
    await waitFor(() => expect(topName()).toBe("First"));
    await waitFor(() => expect(reads(api.calls, "/v1/prices")).toHaveLength(2));
    expect(
      await screen.findByRole("button", {
        name: superPriced("8 Velas"),
      }),
    ).toHaveTextContent(/^8$/);
  });

  it.each(["ALREADY_EXISTS", "NOT_FOUND"])(
    "leaves the card gone after %s: it is gone anyway",
    async (code) => {
      fakeApi({
        "GET /v1/discover": () =>
          page([card({ first_name: "First" }), card({ first_name: "Second" })]),
        "GET /v1/prices": () => json(200, PRICES),
        "POST /v1/swipes": () =>
          envelope(code === "NOT_FOUND" ? 404 : 409, code),
      });
      renderAs("male");
      await screen.findByRole("article", { name: "First" });

      await userEvent.click(screen.getByRole("button", { name: PASS }));

      await act(() => new Promise((r) => setTimeout(r, 30)));
      expect(topName()).toBe("Second");
      expect(noToast()).toBe(true);
    },
  );
});

describe("a screen reader's deck (T-9.11)", () => {
  it("names whoever is on top in each button, Super's price from /prices", async () => {
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card({ first_name: "Second" })]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByRole("article", { name: "First" });

    const row = screen.getByRole("group", {
      name: t("discover.actions.label"),
    });
    expect(
      within(row)
        .getAllByRole("button")
        .map((button) => button.getAttribute("aria-label")),
    ).toEqual(["Pass on First", "Super Like First, 7 Velas", "Like First"]);

    await userEvent.click(
      screen.getByRole("button", { name: "Pass on First" }),
    );
    expect(
      await screen.findByRole("button", { name: "Pass on Second" }),
    ).toBeInTheDocument();
  });

  it.each([
    ["pass", "Pass on First", "Passed on First."],
    ["like", "Like First", "Liked First."],
    ["super", "Super Like First, 7 Velas", "Super liked First."],
  ])("says what a %s did, once it is made", async (_, button, said) => {
    fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card({ first_name: "Second" })]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByRole("article", { name: "First" });
    const statuses = () =>
      screen.getAllByRole("status").map((status) => status.textContent);
    expect(statuses()).not.toContain(said);

    await userEvent.click(screen.getByRole("button", { name: button }));

    expect(statuses()).toContain(said);
  });
});

describe("a man's swipes left today", () => {
  it("says the feed's count before his first swipe, then each swipe's answer", async () => {
    fakeApi({
      "GET /v1/discover": () => page([card(), card()], { left: 50 }),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk({ swipes_left: 49 }),
    });
    renderAs("male");

    expect(
      await screen.findByText(t("discover.swipesLeft.other", { count: 50 })),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: LIKE }));
    expect(
      await screen.findByText(t("discover.swipesLeft.other", { count: 49 })),
    ).toBeInTheDocument();
  });

  it("at the cap: puts the card back, says 0 and asks the API nothing more until tomorrow", async () => {
    const api = fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "First" }), card()], { left: 1 }),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": () =>
        envelope(429, "SWIPE_LIMIT_REACHED", {
          limit: 50,
          resets_at: "2026-10-09T00:00:00+05:30",
        }),
    });
    renderAs("male");
    await screen.findByRole("article", { name: "First" });
    const like = screen.getByRole("button", {
      name: LIKE,
    });

    await userEvent.click(like);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("discover.errors.limit"),
    );
    expect(
      await screen.findByText(t("discover.swipesLeft.other", { count: 0 })),
    ).toBeInTheDocument();
    await waitFor(() => expect(topName()).toBe("First"));
    await userEvent.click(like);
    expect(swipes(api.calls)).toHaveLength(1);
  });
});

describe("pages: the next asked for at 5 left", () => {
  // The plan's number, written out: a test reading PREFETCH_AT would move
  // with it (t65-10 stayed green until this said 5 itself).
  it("asks for the next page when 5 cards are left, not at 6", async () => {
    const api = fakeApi({
      "GET /v1/discover": (call) =>
        call.query.get("cursor") === "c2"
          ? page([card({ first_name: "Later" })])
          : page(
              Array.from({ length: 7 }, () => card()),
              { next: "c2" },
            ),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByTestId("top-card");
    const pass = screen.getByRole("button", {
      name: PASS,
    });

    await userEvent.click(pass);
    await act(() => new Promise((r) => setTimeout(r, 30)));
    expect(reads(api.calls, "/v1/discover")).toHaveLength(1);

    await userEvent.click(pass);
    await waitFor(() =>
      expect(reads(api.calls, "/v1/discover")).toHaveLength(2),
    );
    expect(reads(api.calls, "/v1/discover")[1]?.query.get("cursor")).toBe("c2");
  });
});

describe("the keyboard on desktop: ← pass, → like, ↑ Super Like", () => {
  it.each([
    ["{ArrowRight}", "like", 0],
    ["{ArrowLeft}", "pass", 0],
    ["{ArrowUp}", "super", 7],
  ])("%s sends a %s", async (key, dir, shown) => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByTestId("top-card");
    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: superPriced("7 Velas"),
        }),
      ).toBeEnabled(),
    );

    await userEvent.keyboard(key);

    await waitFor(() => expect(swipes(api.calls)).toHaveLength(1));
    expect(swipes(api.calls)[0]?.body).toEqual(
      expect.objectContaining({ dir, shown_price: shown }),
    );
  });

  it("leaves the keys alone while a sheet is open or something is being typed", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    const field = document.createElement("input");
    document.body.append(field);
    field.focus();
    await userEvent.keyboard("{ArrowRight}");
    field.remove();

    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    document.body.append(dialog);
    await userEvent.keyboard("{ArrowLeft}");
    dialog.remove();

    await act(() => new Promise((r) => setTimeout(r, 30)));
    expect(swipes(api.calls)).toHaveLength(0);
  });
});

describe("dragging the card", () => {
  function drag(element: Element, dx: number, dy: number) {
    const at = (x: number, y: number) => ({
      clientX: x,
      clientY: y,
      pointerId: 1,
      buttons: 1,
      pointerType: "touch",
    });
    fireEvent.pointerDown(element, at(200, 300));
    for (let step = 1; step <= 5; step += 1) {
      fireEvent.pointerMove(
        element,
        at(200 + (dx * step) / 5, 300 + (dy * step) / 5),
      );
    }
    fireEvent.pointerUp(element, { ...at(200 + dx, 300 + dy), buttons: 0 });
  }

  beforeEach(() => {
    Element.prototype.setPointerCapture ??= () => {};
    Element.prototype.releasePointerCapture ??= () => {};
    Element.prototype.hasPointerCapture ??= () => false;
  });

  it.each([
    [160, 0, "like"],
    [-160, 0, "pass"],
    [10, -160, "super"],
  ])("a drag of (%i, %i) past 100 px sends a %s", async (dx, dy, dir) => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByTestId("top-card");
    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: superPriced("7 Velas"),
        }),
      ).toBeEnabled(),
    );

    drag(screen.getByTestId("top-card"), dx, dy);

    await waitFor(() => expect(swipes(api.calls)).toHaveLength(1));
    expect(swipes(api.calls)[0]?.body).toEqual(
      expect.objectContaining({ dir }),
    );
  });

  it("a tap, not a drag, opens the profile at T-6.8's route and swipes nothing", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    drag(screen.getByTestId("top-card"), 0, 0);

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith(
        "/people/00000000-0000-4000-8000-000000000001",
      ),
    );
    expect(swipes(api.calls)).toHaveLength(0);
  });

  // jsdom's events carry no real time, so any drag reads as a fast flick: a
  // nudge under the flick's minimum distance is the one that springs back
  // here. Distance alone, 99 px, is swipeMath.test.ts's.
  it("a nudge springs back and sends nothing", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card({ first_name: "First" }), card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    drag(screen.getByTestId("top-card"), 20, 0);

    await act(() => new Promise((r) => setTimeout(r, 30)));
    expect(swipes(api.calls)).toHaveLength(0);
    expect(topName()).toBe("First");
  });
});

describe("the match sheet ✦", () => {
  async function matchAs(
    gender: "male" | "female",
    thread: Route = () => json(200, { id: "t1" }),
  ) {
    const api = fakeApi({
      "GET /v1/discover": () =>
        page([card({ first_name: "Priya" }), card()], {
          left: gender === "male" ? 50 : null,
        }),
      "GET /v1/prices": () => json(200, PRICES),
      "POST /v1/swipes": swipeOk({ matched: true, match_id: "m1" }),
      "POST /v1/threads": thread,
    });
    renderAs(gender);
    await screen.findByRole("article", { name: "Priya" });
    await userEvent.click(screen.getByRole("button", { name: LIKE }));
    const sheet = await screen.findByRole("dialog", {
      name: t("discover.match.title", { name: "Priya" }),
    });
    return { api, sheet };
  }

  it("offers him the Thread at /prices' price and sends exactly it, then goes to his chats", async () => {
    const { api, sheet } = await matchAs("male");

    const open = await within(sheet).findByRole("button", {
      name: t("discover.match.open", { velas: "9 Velas" }),
    });
    await userEvent.click(open);

    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/chats"));
    expect(api.calls.find((c) => c.path === "/v1/threads")?.body).toEqual({
      match_id: "m1",
      shown_price: 9,
    });
    expect(client.getMutationCache().getAll().at(-1)?.meta).toEqual({
      touchesWallet: true,
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("offers her the Thread free, sending 0, and never says Velas", async () => {
    const { api, sheet } = await matchAs("female");

    expect(sheet).not.toHaveTextContent(/vela/i);
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("discover.match.openFree") }),
    );

    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/chats"));
    expect(api.calls.find((c) => c.path === "/v1/threads")?.body).toEqual({
      match_id: "m1",
      shown_price: 0,
    });
  });

  it("opens the store when he is out of Velas, and stays open", async () => {
    const { sheet } = await matchAs("male", () =>
      envelope(402, "INSUFFICIENT_CREDITS", { required: 9, balance: 5 }),
    );

    await userEvent.click(
      await within(sheet).findByRole("button", {
        name: t("discover.match.open", { velas: "9 Velas" }),
      }),
    );

    await waitFor(() => expect(useStoreSheet.getState().open).toBe(true));
    expect(nav.push).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("says the new price when it changed, and opens nothing", async () => {
    const { sheet } = await matchAs("male", () =>
      envelope(409, "PRICE_CHANGED", { price: 10 }),
    );

    await userEvent.click(
      await within(sheet).findByRole("button", {
        name: t("discover.match.open", { velas: "9 Velas" }),
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("discover.errors.priceChanged", { velas: "10 Velas" }),
    );
    expect(nav.push).not.toHaveBeenCalled();
  });

  it("closes on Keep swiping, the deck still there", async () => {
    const { api, sheet } = await matchAs("male");

    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("discover.match.keepSwiping"),
      }),
    );

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByTestId("top-card")).toBeInTheDocument();
    expect(api.calls.some((c) => c.path === "/v1/threads")).toBe(false);
  });
});

describe("loading, empty and error", () => {
  it("says nobody new is nearby, and looks again", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    expect(
      await screen.findByRole("heading", {
        name: t("discover.empty.nobodyTitle"),
      }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: t("discover.empty.checkAgain") }),
    );
    await waitFor(() =>
      expect(reads(api.calls, "/v1/discover")).toHaveLength(2),
    );
  });

  it("with filters in the URL: asks with them, and when they leave nobody, clears them", async () => {
    nav.search = "intent_ids=1&intent_ids=4&verified=true";
    const api = fakeApi({
      "GET /v1/discover": () => page([]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    expect(
      await screen.findByRole("heading", {
        name: t("discover.empty.filtersTitle"),
      }),
    ).toBeInTheDocument();
    const query = reads(api.calls, "/v1/discover")[0]?.query;
    expect(query?.getAll("intent_ids")).toEqual(["1", "4"]);
    expect(query?.get("verified")).toBe("true");
    await userEvent.click(
      screen.getByRole("button", { name: t("discover.empty.clear") }),
    );
    expect(nav.replace).toHaveBeenCalledWith("/discover");
  });

  it("says when the deck couldn't load, and tries again", async () => {
    let fail = true;
    fakeApi({
      "GET /v1/discover": () =>
        fail
          ? envelope(422, "VALIDATION_ERROR")
          : page([card({ first_name: "Back" })]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    const alert = (await screen.findByText(t("discover.failed"))).closest(
      '[role="alert"]',
    ) as HTMLElement;
    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );
    expect(
      await screen.findByRole("article", { name: "Back" }),
    ).toBeInTheDocument();
  });

  it("switches feeds with the pills, asking for the one pressed", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    const online = screen.getByRole("button", {
      name: t("discover.feeds.online"),
    });
    await userEvent.click(online);

    expect(online).toHaveAttribute("aria-pressed", "true");
    await waitFor(() =>
      expect(reads(api.calls, "/v1/discover").at(-1)?.query.get("feed")).toBe(
        "online",
      ),
    );
    expect(
      screen.getByRole("link", { name: t("discover.search") }),
    ).toHaveAttribute("href", "/discover/search");
  });
});

describe("filters (T-6.9): in the URL, applied by the server", () => {
  const INTENTS = [
    { id: 1, slug: "serious", label: "Something serious" },
    { id: 4, slug: "casual", label: "Casual dating" },
  ];
  const filtersButton = () => screen.getByRole("button", { name: /^Filters/ });

  it("counts each intent and each toggle on the Filters button, and shows no badge with none", async () => {
    nav.search = "intent_ids=1&intent_ids=4&verified=true&online=true";
    fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    let view = renderAs("male");
    await screen.findByTestId("top-card");

    expect(filtersButton()).toHaveAccessibleName(
      t("discover.filters.openCount.other", { count: 4 }),
    );
    expect(screen.getByTestId("filter-count")).toHaveTextContent("4");
    view.unmount();

    nav.search = "online=true";
    view = renderAs("male");
    await screen.findByTestId("top-card");
    expect(filtersButton()).toHaveAccessibleName(
      t("discover.filters.openCount.one"),
    );
    view.unmount();

    nav.search = "";
    renderAs("male");
    await screen.findByTestId("top-card");
    expect(filtersButton()).toHaveAccessibleName(t("discover.filters.open"));
    expect(screen.queryByTestId("filter-count")).toBeNull();
  });

  it("asks the API with every filter in the URL, Online now among them", async () => {
    nav.search = "intent_ids=4&verified=true&online=true";
    const api = fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    const query = reads(api.calls, "/v1/discover")[0]?.query;
    expect(query?.getAll("intent_ids")).toEqual(["4"]);
    expect(query?.get("verified")).toBe("true");
    expect(query?.get("online")).toBe("true");
  });

  it("a change of Online now alone is a new scroll, asked for afresh", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    const { rerender } = renderAs("male");
    await screen.findByTestId("top-card");

    nav.search = "online=true";
    rerender(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <DiscoverScreen />
        </ToastProvider>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(reads(api.calls, "/v1/discover")).toHaveLength(2),
    );
    expect(reads(api.calls, "/v1/discover")[1]?.query.get("online")).toBe(
      "true",
    );
  });

  it("asks with no filter at all when the URL has none", async () => {
    const api = fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    const query = reads(api.calls, "/v1/discover")[0]?.query;
    expect(query?.has("intent_ids")).toBe(false);
    expect(query?.has("verified")).toBe(false);
    expect(query?.has("online")).toBe(false);
  });

  it("opens the sheet from the URL's filters, and Show people writes the draft to the URL, asking nothing while open", async () => {
    nav.search = "intent_ids=1";
    const api = fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "GET /v1/intents": () => json(200, INTENTS),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    await userEvent.click(filtersButton());
    const dialog = screen.getByRole("dialog");
    const serious = await within(dialog).findByRole("button", {
      name: "Something serious",
    });
    expect(serious).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Casual dating" }),
    );
    await userEvent.click(
      within(dialog).getByRole("switch", {
        name: t("discover.filters.selfie"),
      }),
    );
    await userEvent.click(
      within(dialog).getByRole("switch", {
        name: t("discover.filters.online"),
      }),
    );
    expect(reads(api.calls, "/v1/discover")).toHaveLength(1);
    expect(nav.replace).not.toHaveBeenCalled();

    await userEvent.click(
      within(dialog).getByRole("button", { name: t("discover.filters.show") }),
    );
    expect(nav.replace).toHaveBeenCalledExactlyOnceWith(
      "/discover?intent_ids=1&intent_ids=4&verified=true&online=true",
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("writes /discover alone when the sheet's Clear is shown", async () => {
    nav.search = "intent_ids=1&verified=true&online=true";
    fakeApi({
      "GET /v1/discover": () => page([card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "GET /v1/intents": () => json(200, INTENTS),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    await userEvent.click(filtersButton());
    const dialog = screen.getByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: t("discover.filters.clear") }),
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: t("discover.filters.show") }),
    );
    expect(nav.replace).toHaveBeenCalledExactlyOnceWith("/discover");
  });

  it("closing the sheet writes nothing, and the keys stay with it while open", async () => {
    nav.search = "verified=true";
    const api = fakeApi({
      "GET /v1/discover": () => page([card(), card()]),
      "GET /v1/prices": () => json(200, PRICES),
      "GET /v1/intents": () => json(200, INTENTS),
      "POST /v1/swipes": swipeOk(),
    });
    renderAs("male");
    await screen.findByTestId("top-card");

    await userEvent.click(filtersButton());
    await userEvent.click(
      screen.getByRole("switch", { name: t("discover.filters.online") }),
    );
    await userEvent.keyboard("{ArrowRight}");
    expect(swipes(api.calls)).toHaveLength(0);
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(nav.replace).not.toHaveBeenCalled();
    await userEvent.click(filtersButton());
    expect(
      screen.getByRole("switch", { name: t("discover.filters.online") }),
    ).toHaveAttribute("aria-checked", "false");
  });

  it("the empty deck's Clear filters writes /discover alone, Online now included", async () => {
    nav.search = "online=true";
    fakeApi({
      "GET /v1/discover": () => page([]),
      "GET /v1/prices": () => json(200, PRICES),
    });
    renderAs("male");

    await userEvent.click(
      await screen.findByRole("button", { name: t("discover.empty.clear") }),
    );
    expect(nav.replace).toHaveBeenCalledExactlyOnceWith("/discover");
  });
});
