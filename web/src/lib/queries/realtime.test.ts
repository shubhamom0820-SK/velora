import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "@/types/api";

import { queryKeys } from "./keys";
import type { Message } from "./messages";
import { makeQueryClient } from "./QueryProvider";
import { afterReconnect, applyEvent, TYPING_SHOWN_MS } from "./realtime";

type MessagePage = components["schemas"]["MessagePage"];
type ThreadRowPage = components["schemas"]["ThreadRowPage"];

const T = "t1";
const HIS = "male" as const;
const HERS = "female" as const;

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: "m1",
    thread_id: T,
    kind: "text",
    body: "Hello",
    masked: false,
    duration_s: null,
    mine: false,
    from_deleted_account: false,
    locked: false,
    read_at: null,
    created_at: "2026-10-09T10:00:00Z",
    client_msg_id: null,
    ...overrides,
  };
}

function event(type: string, data: Record<string, unknown>) {
  return { type, id: crypto.randomUUID(), data };
}

function pages(items: Message[]): InfiniteData<MessagePage> {
  return {
    pages: [{ items, next_cursor: null }],
    pageParams: [null],
  };
}

/** A row in her list, with the expiry the API never sends her. */
const ROW = {
  id: T,
  origin: "match",
  status: "active",
  expires_at: null,
  knotted_at: null,
  i_tied: false,
  unread: 0,
  last_message: null,
  last_message_at: null,
  other: {
    id: "u2",
    first_name: "Arjun",
    username: "arjun",
    main_photo_url: null,
    shows_badge: false,
    is_online: false,
    deleted: false,
  },
};
const LIST = queryKeys.threadList("threads", "all", "");

let client: QueryClient;

/** Whether `key`'s query has been marked stale since it was set. */
const stale = (key: readonly unknown[]) =>
  client.getQueryState(key)?.isInvalidated === true;

beforeEach(() => {
  vi.useFakeTimers();
  client = makeQueryClient();
});

afterEach(() => {
  vi.useRealTimers();
  client.clear();
});

describe("message.new", () => {
  it("puts their message at the front of its Thread, once, and asks the lists again", () => {
    client.setQueryData(queryKeys.messages(T), pages([message({ id: "m0" })]));
    client.setQueryData(LIST, { pages: [{ items: [ROW] }], pageParams: [] });
    const arrived = message({ id: "m2", body: "Hi" });

    applyEvent(
      client,
      event("message.new", { thread_id: T, message: arrived }),
      HERS,
    );
    applyEvent(
      client,
      event("message.new", { thread_id: T, message: arrived }),
      HERS,
    );

    const items = client
      .getQueryData<InfiniteData<MessagePage>>(queryKeys.messages(T))
      ?.pages[0]?.items.map((item) => item.id);
    expect(items).toEqual(["m2", "m0"]);
    expect(stale(LIST)).toBe(true);
  });

  it("ends their typing dots when their message lands; mine leaves them", () => {
    applyEvent(client, event("typing", { thread_id: T }), HERS);
    applyEvent(
      client,
      event("message.new", { thread_id: T, message: message({ mine: true }) }),
      HERS,
    );
    expect(client.getQueryData(queryKeys.typing(T))).toBe(true);

    applyEvent(
      client,
      event("message.new", { thread_id: T, message: message({ id: "m3" }) }),
      HERS,
    );
    expect(client.getQueryData(queryKeys.typing(T))).toBe(false);
  });

  it("ignores one without a message", () => {
    client.setQueryData(queryKeys.messages(T), pages([]));

    applyEvent(client, event("message.new", { thread_id: T }), HERS);

    expect(
      client.getQueryData<InfiniteData<MessagePage>>(queryKeys.messages(T))
        ?.pages[0]?.items,
    ).toEqual([]);
  });
});

describe("message.read", () => {
  it("marks mine read up to the one they read, never theirs or later ones", () => {
    client.setQueryData(
      queryKeys.messages(T),
      pages([
        message({
          id: "later",
          mine: true,
          created_at: "2026-10-09T10:05:00Z",
        }),
        message({
          id: "theirs",
          mine: false,
          created_at: "2026-10-09T10:03:00Z",
        }),
        message({ id: "read", mine: true, created_at: "2026-10-09T10:02:00Z" }),
        message({
          id: "earlier",
          mine: true,
          created_at: "2026-10-09T10:01:00Z",
        }),
      ]),
    );
    const at = "2026-10-09T10:04:00Z";

    applyEvent(
      client,
      event("message.read", {
        thread_id: T,
        up_to_message_id: "read",
        read_at: at,
      }),
      HIS,
    );

    const read = Object.fromEntries(
      (
        client.getQueryData<InfiniteData<MessagePage>>(queryKeys.messages(T))
          ?.pages[0]?.items ?? []
      ).map((item) => [item.id, item.read_at]),
    );
    expect(read).toEqual({ later: null, theirs: null, read: at, earlier: at });
  });
});

describe("typing", () => {
  it("shows the dots, and lets them go 6 s after the last", () => {
    applyEvent(client, event("typing", { thread_id: T }), HIS);
    expect(client.getQueryData(queryKeys.typing(T))).toBe(true);
    vi.advanceTimersByTime(5_000);
    applyEvent(client, event("typing", { thread_id: T }), HIS);
    vi.advanceTimersByTime(5_999);
    expect(client.getQueryData(queryKeys.typing(T))).toBe(true);

    vi.advanceTimersByTime(1);

    expect(client.getQueryData(queryKeys.typing(T))).toBe(false);
    expect(TYPING_SHOWN_MS).toBe(6_000);
  });
});

describe("the hour's events are his alone (P-460, D-554)", () => {
  it.each(["thread.expiring", "thread.expired"])(
    "%s reaching her changes nothing and asks nothing, even carrying an expiry",
    (type) => {
      client.setQueryData(queryKeys.thread(T), { ...ROW, expires_at: null });
      client.setQueryData(LIST, { pages: [{ items: [ROW] }], pageParams: [] });
      const fetches = vi.spyOn(client, "invalidateQueries");

      applyEvent(
        client,
        event(type, { thread_id: T, expires_at: "2026-10-09T11:00:00Z" }),
        HERS,
      );

      expect(fetches).not.toHaveBeenCalled();
      expect(client.getQueryData(queryKeys.thread(T))).toEqual({
        ...ROW,
        expires_at: null,
      });
      const rows = client.getQueryData<InfiniteData<ThreadRowPage>>(LIST);
      expect(rows?.pages[0]?.items[0]?.expires_at).toBeNull();
    },
  );

  it.each(["thread.expiring", "thread.expired"])(
    "%s reaching someone whose gender isn't known yet changes nothing",
    (type) => {
      const fetches = vi.spyOn(client, "invalidateQueries");

      applyEvent(client, event(type, { thread_id: T }), undefined);

      expect(fetches).not.toHaveBeenCalled();
    },
  );

  it.each(["thread.expiring", "thread.expired"])(
    "%s reaching him asks his Thread and lists again, writing nothing itself",
    (type) => {
      client.setQueryData(queryKeys.thread(T), { ...ROW });
      client.setQueryData(LIST, { pages: [{ items: [ROW] }], pageParams: [] });

      applyEvent(
        client,
        event(type, { thread_id: T, expires_at: "2026-10-09T11:00:00Z" }),
        HIS,
      );

      expect(stale(queryKeys.thread(T))).toBe(true);
      expect(stale(LIST)).toBe(true);
      expect(client.getQueryData(queryKeys.thread(T))).toEqual(ROW);
    },
  );

  it("never writes an expiry into her cache from any event", () => {
    client.setQueryData(queryKeys.thread(T), { ...ROW });
    for (const type of [
      "thread.opened",
      "knot.requested",
      "knot.accepted",
      "knot.untied",
    ]) {
      applyEvent(
        client,
        event(type, { thread_id: T, expires_at: "2026-10-09T11:00:00Z" }),
        HERS,
      );
    }

    expect(client.getQueryData(queryKeys.thread(T))).toEqual(ROW);
    expect(stale(queryKeys.thread(T))).toBe(true);
  });
});

describe("the rest", () => {
  it.each(["thread.opened", "knot.requested", "knot.accepted", "knot.untied"])(
    "%s asks the Thread and every list again",
    (type) => {
      client.setQueryData(queryKeys.thread(T), { ...ROW });
      client.setQueryData(LIST, { pages: [], pageParams: [] });

      applyEvent(client, event(type, { thread_id: T }), HERS);

      expect(stale(queryKeys.thread(T))).toBe(true);
      expect(stale(LIST)).toBe(true);
    },
  );

  it("wallet.updated sets his balance at once and asks the history again", () => {
    client.setQueryData(queryKeys.wallet(), { balance: 3 });
    client.setQueryData(queryKeys.walletLedger(), {
      pages: [],
      pageParams: [],
    });

    applyEvent(client, event("wallet.updated", { balance: 8 }), HIS);

    expect(client.getQueryData(queryKeys.wallet())).toEqual({ balance: 8 });
    expect(stale(queryKeys.walletLedger())).toBe(true);
  });

  it("wallet.updated with no whole balance changes nothing", () => {
    client.setQueryData(queryKeys.wallet(), { balance: 3 });

    applyEvent(client, event("wallet.updated", { balance: "8" }), HIS);
    applyEvent(client, event("wallet.updated", { balance: 8.5 }), HIS);

    expect(client.getQueryData(queryKeys.wallet())).toEqual({ balance: 3 });
  });

  it.each([
    ["match.created", { match_id: "x", user_id: "u2" }, queryKeys.likes()],
    [
      "album.decided",
      { album_request_id: "r", user_id: "u2", granted: true },
      queryKeys.album("u2"),
    ],
    [
      "gift.received",
      { gift_send_id: "g", gift_id: "rose", user_id: "u2" },
      queryKeys.receivedGifts(),
    ],
  ] as const)("%s asks what it changed again", (type, data, key) => {
    client.setQueryData(key, {});
    client.setQueryData(queryKeys.notifications(), {});
    client.setQueryData(queryKeys.notificationPrefs(), {});

    applyEvent(client, event(type, data), HERS);

    expect(stale(key)).toBe(true);
    expect(stale(queryKeys.notifications())).toBe(true);
    // The list alone: not the push settings beneath its key.
    expect(stale(queryKeys.notificationPrefs())).toBe(false);
  });

  it("an event this build doesn't know changes nothing", () => {
    const fetches = vi.spyOn(client, "invalidateQueries");
    const writes = vi.spyOn(client, "setQueryData");

    applyEvent(client, event("call.ringing", { thread_id: T }), HIS);

    expect(fetches).not.toHaveBeenCalled();
    expect(writes).not.toHaveBeenCalled();
  });
});

describe("after a reconnect", () => {
  it("asks every Thread query and the wallet again", () => {
    client.setQueryData(queryKeys.thread(T), {});
    client.setQueryData(queryKeys.messages(T), pages([]));
    client.setQueryData(LIST, { pages: [], pageParams: [] });
    client.setQueryData(queryKeys.wallet(), { balance: 1 });

    afterReconnect(client);

    for (const key of [
      queryKeys.thread(T),
      queryKeys.messages(T),
      LIST,
      queryKeys.wallet(),
    ]) {
      expect(stale(key)).toBe(true);
    }
  });
});
