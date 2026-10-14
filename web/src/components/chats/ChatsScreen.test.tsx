import { QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { queryKeys } from "@/lib/queries/keys";
import type { ThreadRow } from "@/lib/queries/threads";
import {
  envelope,
  fakeApi,
  json,
  type Call,
  type Route,
} from "@/lib/testing/fakeApi";

import { ChatsScreen } from "./ChatsScreen";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/chats",
}));

const MINUTE = 60_000;
const inMinutes = (minutes: number) =>
  new Date(Date.now() + minutes * MINUTE).toISOString();

function row(id: string, overrides: Partial<ThreadRow> = {}): ThreadRow {
  return {
    id,
    origin: "match",
    status: "active",
    expires_at: null,
    knotted_at: null,
    i_tied: false,
    unread: 0,
    last_message: {
      kind: "text",
      text: `Hello from ${id}`,
      mine: false,
      at: "2026-10-09T11:00:00Z",
    },
    last_message_at: "2026-10-09T11:00:00Z",
    other: {
      id: `u-${id}`,
      first_name: `Name ${id}`,
      username: `user_${id}`,
      main_photo_url: null,
      shows_badge: false,
      is_online: false,
      deleted: false,
    },
    ...overrides,
  };
}

const page = (items: ThreadRow[], next_cursor: string | null = null) =>
  json(200, { items, next_cursor });

/** The list by tier, filter and q; anything not given is an empty page. */
function lists(
  byTier: { threads?: ThreadRow[]; knots?: ThreadRow[] },
  overrides: Record<string, Route> = {},
) {
  return fakeApi({
    "GET /v1/threads": (call) =>
      page(byTier[call.query.get("tier") as "threads" | "knots"] ?? []),
    ...overrides,
  });
}

function renderChats(gender: "male" | "female" | null) {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  if (gender) client.setQueryData(queryKeys.me(), { id: "me", gender });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ChatsScreen />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const listOf = async () =>
  within(await screen.findByRole("region", { name: t("chats.threads") }));
const rowNamed = async (name: string) =>
  (await screen.findByText(name)).closest("li") as HTMLElement;
const threadGets = (calls: Call[], tier = "threads") =>
  calls.filter(
    (call) =>
      call.method === "GET" &&
      call.path === "/v1/threads" &&
      call.query.get("tier") === tier,
  );
const COUNTDOWN = /\d+[hm] left$|^Ran out$/;

let observed: IntersectionObserverCallback[] = [];

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  observed = [];
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: IntersectionObserverCallback) {
        observed.push(callback);
      }
      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords() {
        return [];
      }
    },
  );
  nav.push.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("her chats say nothing about time (D-097, D-554, P-460)", () => {
  // The API sends her `expires_at` as null; these rows carry one anyway, so
  // the screen's own allowlist is what keeps it off her screen.
  const hers = [
    row("t1", { expires_at: inMinutes(41) }),
    row("t2", { status: "expired", expires_at: inMinutes(-5) }),
    row("t3", { status: "expired", expires_at: null }),
  ];

  it("draws no countdown and no expired state on her rows, whatever they carry", async () => {
    lists({ threads: hers });
    renderChats("female");

    const list = await listOf();
    expect(list.getAllByRole("listitem")).toHaveLength(3);
    expect(list.queryByText(COUNTDOWN)).toBeNull();
    expect(document.querySelector("[data-phase]")).toBeNull();
    // Her expired Thread reads as any other: its name in ink, its preview.
    const expired = await rowNamed("Name t2");
    expect(within(expired).getByText("Name t2")).toHaveClass("text-ink");
    expect(within(expired).getByText("Hello from t2")).toBeInTheDocument();
  });

  it("offers her no Clear expired and no footer about the hour", async () => {
    lists({ threads: hers });
    renderChats("female");

    await listOf();
    await screen.findByText("Name t1");
    expect(screen.queryByRole("button", { name: /clear expired/i })).toBeNull();
    expect(screen.queryByText(t("chats.footer"))).toBeNull();
    expect(screen.queryByText(/hour|ran out|expired/i)).toBeNull();
  });

  it("shows nobody a countdown while it isn't yet known that he is a man", async () => {
    lists(
      { threads: [row("t1", { expires_at: inMinutes(41) })] },
      { "GET /v1/me": () => new Promise<Response>(() => {}) },
    );
    renderChats(null);

    await screen.findByText("Name t1");
    expect(screen.queryByText(COUNTDOWN)).toBeNull();
    expect(screen.queryByText(t("chats.footer"))).toBeNull();
  });
});

describe("his chats (08-DESIGN §8)", () => {
  it("draws his countdowns by the clock, and none on a Thread that never expires", async () => {
    lists({
      threads: [
        row("t1", { expires_at: inMinutes(41.5) }),
        // Still `active` in the row, but past its time: the clock decides.
        row("t2", { expires_at: inMinutes(-1) }),
        // A private message never expires (D-550): no pill.
        row("t3", { origin: "dm", expires_at: null }),
      ],
    });
    renderChats("male");

    expect(
      within(await rowNamed("Name t1")).getByText("42m left"),
    ).toBeInTheDocument();
    expect(
      within(await rowNamed("Name t2")).getByText("Ran out"),
    ).toBeInTheDocument();
    expect(within(await rowNamed("Name t3")).queryByText(COUNTDOWN)).toBeNull();
    expect(screen.getByText(t("chats.footer"))).toBeInTheDocument();
  });

  it("counts Clear expired by the clock, and asks the server to clear what it counts", async () => {
    const api = lists(
      {
        threads: [
          row("t1", { expires_at: inMinutes(-3) }),
          row("t2", { status: "expired", expires_at: inMinutes(-90) }),
          row("t3", { expires_at: inMinutes(30) }),
        ],
      },
      { "POST /v1/threads/clear": () => json(200, { cleared: 2 }) },
    );
    renderChats("male");

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("chats.clearExpired", { count: 2 }),
      }),
    );

    await waitFor(() =>
      expect(
        api.calls.find((call) => call.path === "/v1/threads/clear")?.body,
      ).toEqual({ expired: true }),
    );
    expect(
      await screen.findByText(t("chats.clearedMany.other", { count: 2 })),
    ).toBeInTheDocument();
  });

  it("shows no Clear expired when nothing has run out", async () => {
    lists({ threads: [row("t1", { expires_at: inMinutes(30) })] });
    renderChats("male");

    await screen.findByText("Name t1");
    expect(screen.queryByRole("button", { name: /clear expired/i })).toBeNull();
  });
});

describe("the rows", () => {
  it("opens the Thread, names a voice note, and says when nothing's been written", async () => {
    lists({
      threads: [
        row("t1", {
          last_message: {
            kind: "voice",
            text: null,
            mine: false,
            at: "2026-10-09T11:00:00Z",
          },
        }),
        row("t2", { last_message: null }),
      ],
    });
    renderChats("male");

    const voice = await rowNamed("Name t1");
    expect(within(voice).getByRole("link")).toHaveAttribute(
      "href",
      "/chats/t1",
    );
    expect(within(voice).getByText(t("chats.voiceNote"))).toBeInTheDocument();
    expect(
      within(await rowNamed("Name t2")).getByText(t("chats.noMessages")),
    ).toBeInTheDocument();
  });

  it("dots a row with something unread, and only that row", async () => {
    lists({ threads: [row("t1", { unread: 3 }), row("t2", { unread: 0 })] });
    renderChats("female");

    expect(
      within(await rowNamed("Name t1")).getByRole("img", {
        name: t("chats.unread.other", { count: 3 }),
      }),
    ).toBeInTheDocument();
    expect(
      within(await rowNamed("Name t2")).queryByRole("img", { name: /unread/ }),
    ).toBeNull();
  });

  it("shows a deleted account with no name or photo", async () => {
    lists({
      threads: [
        row("t1", {
          other: {
            id: "u-t1",
            first_name: null,
            username: null,
            main_photo_url: null,
            shows_badge: false,
            is_online: false,
            deleted: true,
          },
        }),
      ],
    });
    renderChats("male");

    const gone = await rowNamed(t("chats.deletedAccount"));
    expect(gone.querySelector("img")).toBeNull();
  });

  it("puts Knots on their own tab, each with the knot glyph and no countdown", async () => {
    const api = lists({
      threads: [row("t1", { expires_at: inMinutes(30) })],
      knots: [
        row("k1", {
          status: "knotted",
          knotted_at: "2026-10-04T10:00:00Z",
          expires_at: null,
        }),
      ],
    });
    renderChats("male");

    await screen.findByText("Name t1");
    expect(screen.queryByText("Name k1")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /^Knots/ }));
    const knot = await rowNamed("Name k1");
    expect(
      within(knot).getByRole("img", { name: t("chats.knot") }),
    ).toBeInTheDocument();
    expect(within(knot).queryByText(COUNTDOWN)).toBeNull();
    expect(screen.queryByText("Name t1")).toBeNull();
    expect(threadGets(api.calls, "knots").length).toBeGreaterThan(0);
  });
});

describe("the tabs' counts", () => {
  it("counts one page of each tier, and says 50+ when there are more", async () => {
    const fifty = Array.from({ length: 50 }, (_, n) =>
      row(`k${n}`, { status: "knotted" }),
    );
    const api = fakeApi({
      "GET /v1/threads": (call) =>
        call.query.get("tier") === "knots"
          ? page(fifty, "next")
          : page([row("t1"), row("t2"), row("t3")]),
    });
    renderChats("female");

    expect(
      await screen.findByRole("button", {
        name: t("chats.tabCount", { tab: t("chats.threads"), count: 3 }),
      }),
    ).toBeInTheDocument();
    const knots = await screen.findByRole("button", {
      name: t("chats.tabCountOver", { tab: t("chats.knots"), count: 50 }),
    });
    expect(knots).toHaveTextContent("50+");
    // A page is 50 (`THREADS_PAGE`, the API's largest).
    for (const call of api.calls) expect(call.query.get("limit")).toBe("50");
  });
});

describe("clearing one, with 5 s to undo it", () => {
  it("takes the row out at once, then offers Undo, which brings it back", async () => {
    let cleared = false;
    let answer: (response: Response) => void = () => {};
    const api = fakeApi({
      "GET /v1/threads": (call) =>
        page(
          call.query.get("tier") === "threads"
            ? cleared
              ? [row("t2")]
              : [row("t1"), row("t2")]
            : [],
        ),
      "POST /v1/threads/t1/clear": () =>
        new Promise<Response>((resolve) => {
          answer = (response) => {
            cleared = true;
            resolve(response);
          };
        }),
      "DELETE /v1/threads/t1/clear": () => {
        cleared = false;
        return json(204);
      },
    });
    renderChats("male");

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("chats.clearRow", { name: "Name t1" }),
      }),
    );
    // Gone while the server is still answering.
    await waitFor(() => expect(screen.queryByText("Name t1")).toBeNull());
    expect(screen.queryByRole("button", { name: t("chats.undo") })).toBeNull();

    act(() => answer(json(204)));
    expect(await screen.findByText(t("chats.cleared"))).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: t("chats.undo") }),
    );
    expect(await screen.findByText("Name t1")).toBeInTheDocument();
    expect(api.sent()).toContain("DELETE /v1/threads/t1/clear");
  });

  it("offers Undo for exactly 5 s, then sends nothing more", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const api = lists(
      { threads: [row("t1")] },
      { "POST /v1/threads/t1/clear": () => json(204) },
    );
    renderChats("male");

    await user.click(
      await screen.findByRole("button", {
        name: t("chats.clearRow", { name: "Name t1" }),
      }),
    );
    await screen.findByRole("button", { name: t("chats.undo") });

    act(() => vi.advanceTimersByTime(4900));
    expect(
      screen.getByRole("button", { name: t("chats.undo") }),
    ).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(100));
    expect(screen.queryByRole("button", { name: t("chats.undo") })).toBeNull();
    expect(api.sent()).not.toContain("DELETE /v1/threads/t1/clear");
  });

  it.each([
    ["NOT_FOUND", 404],
    ["RATE_LIMITED", 429],
  ])(
    "puts the row back and says so when the clear is refused (%s)",
    async (code, status) => {
      let gets = 0;
      lists(
        {},
        {
          // After the refusal the list isn't answered again: only the row put
          // back by the screen can show it.
          "GET /v1/threads": (call) => {
            if (call.query.get("tier") !== "threads") return page([]);
            gets += 1;
            return gets === 1
              ? page([row("t1")])
              : new Promise<Response>(() => {});
          },
          "POST /v1/threads/t1/clear": () => envelope(status, code),
        },
      );
      renderChats("male");

      await userEvent.click(
        await screen.findByRole("button", {
          name: t("chats.clearRow", { name: "Name t1" }),
        }),
      );

      expect(
        await screen.findByText(t("chats.clearFailed")),
      ).toBeInTheDocument();
      expect(screen.getByText("Name t1")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: t("chats.undo") }),
      ).toBeNull();
    },
  );
});

describe("select mode", () => {
  it("clears exactly the chats chosen, in one request, and leaves select mode", async () => {
    const api = lists(
      { threads: [row("t1"), row("t2"), row("t3")] },
      { "POST /v1/threads/clear": () => json(200, { cleared: 2 }) },
    );
    renderChats("male");

    await userEvent.click(
      await screen.findByRole("button", { name: t("chats.select") }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: t("chats.selectRow", { name: "Name t1" }),
      }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: t("chats.selectRow", { name: "Name t3" }),
      }),
    );
    await userEvent.click(
      screen.getByRole("button", {
        name: t("chats.clearSelected.other", { count: 2 }),
      }),
    );

    await waitFor(() =>
      expect(
        api.calls.find((call) => call.path === "/v1/threads/clear")?.body,
      ).toEqual({ thread_ids: ["t1", "t3"] }),
    );
    expect(
      await screen.findByText(t("chats.clearedMany.other", { count: 2 })),
    ).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("takes at most 100 at a time, as the API does", async () => {
    lists({
      threads: Array.from({ length: 101 }, (_, n) => row(`t${n}`)),
    });
    renderChats("female");

    fireEvent.click(
      await screen.findByRole("button", { name: t("chats.select") }),
    );
    const boxes = screen.getAllByRole("checkbox");
    for (const box of boxes.slice(0, 100)) fireEvent.click(box);

    expect(boxes[100]).toBeDisabled();
    expect(boxes[99]).toBeEnabled();
    expect(
      screen.getByText(t("chats.selectLimit", { max: 100 })),
    ).toBeInTheDocument();
    // Its own timeout, this test's only (P-802): the claim needs a hundred real
    // selections, and React renders after each click whatever wraps them, so it
    // can't be made cheaper. About 0.5 s alone; 9.7 s and 22.4 s measured at load
    // averages 16 and 85, failing unrelated landings at the global 5 s.
  }, 30_000);
});

describe("search and the Knots' filters", () => {
  it("asks by name, trimmed, and never sends an empty search", async () => {
    const api = fakeApi({
      "GET /v1/threads": (call) =>
        page(
          call.query.get("tier") === "threads" && !call.query.has("q")
            ? [row("t1")]
            : [],
        ),
    });
    renderChats("male");

    const search = await screen.findByRole("searchbox", {
      name: t("chats.search"),
    });
    await userEvent.type(search, "   ");
    await new Promise((resolve) => setTimeout(resolve, 400));
    for (const call of threadGets(api.calls)) {
      expect(call.query.has("q")).toBe(false);
    }

    await userEvent.type(search, "Pri  ");
    await waitFor(() =>
      expect(
        threadGets(api.calls).some((call) => call.query.get("q") === "Pri"),
      ).toBe(true),
    );
    expect(await screen.findByText(t("chats.noResults"))).toBeInTheDocument();
    for (const call of threadGets(api.calls)) {
      expect(call.query.get("q")).not.toBe("   Pri  ");
    }
  });

  it("never sends more than the API takes: 50 characters", async () => {
    const api = lists({ threads: [row("t1")] });
    renderChats("male");

    const search = await screen.findByRole("searchbox", {
      name: t("chats.search"),
    });
    fireEvent.change(search, { target: { value: "x".repeat(60) } });
    await waitFor(() =>
      expect(threadGets(api.calls).some((call) => call.query.has("q"))).toBe(
        true,
      ),
    );
    for (const call of threadGets(api.calls)) {
      expect((call.query.get("q") ?? "").length).toBeLessThanOrEqual(50);
    }
  });

  it("filters Knots alone, and a filter chosen there never reaches Threads", async () => {
    const api = lists({
      threads: [row("t1")],
      knots: [row("k1", { status: "knotted" })],
    });
    renderChats("male");

    await screen.findByText("Name t1");
    expect(
      screen.queryByRole("group", { name: t("chats.filters") }),
    ).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /^Knots/ }));
    await userEvent.click(
      await screen.findByRole("button", { name: t("chats.filterUnread") }),
    );
    await waitFor(() =>
      expect(
        threadGets(api.calls, "knots").some(
          (call) => call.query.get("filter") === "unread",
        ),
      ).toBe(true),
    );

    await userEvent.click(screen.getByRole("button", { name: /^Threads/ }));
    await screen.findByText("Name t1");
    for (const call of threadGets(api.calls)) {
      expect(call.query.get("filter")).toBe("all");
    }
  });
});

describe("loading, empty and error", () => {
  it("is busy with placeholders while the list loads", async () => {
    fakeApi({ "GET /v1/threads": () => new Promise<Response>(() => {}) });
    renderChats("male");

    expect(
      screen.getByRole("region", { name: t("chats.threads") }),
    ).toHaveAttribute("aria-busy", "true");
  });

  it("says there are no threads yet, and sends him to Discover", async () => {
    lists({});
    renderChats("male");

    expect(
      await screen.findByText(t("chats.emptyThreads")),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: t("chats.emptyAction") }),
    );
    expect(nav.push).toHaveBeenCalledWith("/discover");
    // Nothing to search or select in an empty list.
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(
      screen.queryByRole("button", { name: t("chats.select") }),
    ).toBeNull();
  });

  it("says there are no knots yet", async () => {
    lists({ threads: [row("t1")] });
    renderChats("female");

    await userEvent.click(
      await screen.findByRole("button", { name: /^Knots/ }),
    );
    expect(await screen.findByText(t("chats.emptyKnots"))).toBeInTheDocument();
  });

  it("says when the list failed, and tries again", async () => {
    let fail = true;
    lists(
      {},
      {
        "GET /v1/threads": (call) =>
          call.query.get("tier") !== "threads"
            ? page([])
            : fail
              ? envelope(500, "INTERNAL")
              : page([row("t1")]),
      },
    );
    renderChats("male");

    expect(await screen.findByText(t("chats.failed"))).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));
    expect(await screen.findByText("Name t1")).toBeInTheDocument();
  });

  it("asks for the next page near the end, and says when that fails", async () => {
    let second = 0;
    const api = fakeApi({
      "GET /v1/threads": (call) => {
        if (call.query.get("tier") !== "threads") return page([]);
        if (call.query.get("cursor") !== "c2") return page([row("t1")], "c2");
        second += 1;
        return second === 1 ? envelope(500, "INTERNAL") : page([row("t2")]);
      },
    });
    renderChats("male");

    await screen.findByText("Name t1");
    act(() => {
      for (const callback of observed) {
        callback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    });

    expect(await screen.findByText(t("chats.failed"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));
    expect(await screen.findByText("Name t2")).toBeInTheDocument();
    expect(
      threadGets(api.calls).filter((call) => call.query.get("cursor") === "c2"),
    ).toHaveLength(2);
  });
});
