import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  backoffDelay,
  CLOSE,
  parseEvent,
  Realtime,
  socketUrl,
  type RealtimeEvent,
} from "./ws";

// The plan's numbers, written out (T-7.12): a test reading the code's own
// constants would move with them.
const SECOND = 1_000;
const FIRST_WAIT = 1 * SECOND;
const MOST_WAIT = 30 * SECOND;
const PING = 25 * SECOND;
const PONG = 10 * SECOND;
const HIDDEN = 5 * 60 * SECOND;

class FakeSocket {
  readyState = 0;
  sent: unknown[] = [];
  closedWith: number | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;

  constructor(readonly url: string) {}

  send(text: string) {
    this.sent.push(JSON.parse(text));
  }
  close(code: number) {
    this.closedWith = code;
    this.readyState = 3;
  }
  // What the server does.
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  say(type: string, data: Record<string, unknown> = {}) {
    this.onmessage?.({ data: JSON.stringify({ type, id: "e1", data }) });
  }
  shut(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

class FakePage {
  visibilityState: DocumentVisibilityState = "visible";
  private listeners = new Set<() => void>();
  addEventListener(_: "visibilitychange", listener: () => void) {
    this.listeners.add(listener);
  }
  removeEventListener(_: "visibilitychange", listener: () => void) {
    this.listeners.delete(listener);
  }
  set(state: DocumentVisibilityState) {
    this.visibilityState = state;
    for (const listener of this.listeners) listener();
  }
}

function harness({ random = 0.999999 } = {}) {
  const sockets: FakeSocket[] = [];
  const events: RealtimeEvent[] = [];
  const ticket = vi.fn(async () => `ticket-${ticket.mock.calls.length}`);
  const onReconnect = vi.fn();
  const page = new FakePage();
  const realtime = new Realtime({
    onEvent: (event) => events.push(event),
    onReconnect,
    ticket,
    open: (url) => {
      const socket = new FakeSocket(url);
      sockets.push(socket);
      return socket as unknown as WebSocket;
    },
    random: () => random,
    page,
  });
  const last = () => sockets.at(-1) as FakeSocket;
  return { realtime, sockets, events, ticket, onReconnect, page, last };
}

/** Lets the ticket's promise settle and a socket be made. */
async function settle() {
  await vi.advanceTimersByTimeAsync(0);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
});

describe("where it connects", () => {
  it("asks a ticket, then opens wss:// on the API's host with it", async () => {
    const { realtime, last, ticket } = harness();
    realtime.start();
    await settle();

    expect(ticket).toHaveBeenCalledTimes(1);
    expect(last().url).toBe("wss://api.test/ws?ticket=ticket-1");
    realtime.stop();
  });

  it("uses ws:// for a local http:// API", () => {
    expect(socketUrl("abc", "http://127.0.0.1:8000")).toBe(
      "ws://127.0.0.1:8000/ws?ticket=abc",
    );
    expect(socketUrl("abc", "https://api.staging.example/")).toBe(
      "wss://api.staging.example/ws?ticket=abc",
    );
  });
});

describe("backing off (1 s to 30 s, with jitter)", () => {
  it("waits between half of each ceiling and all of it, doubling to 30 s", () => {
    const ceilings = [1, 2, 4, 8, 16, 30, 30].map((s) => s * SECOND);
    ceilings.forEach((ceiling, attempt) => {
      expect(backoffDelay(attempt, 0)).toBe(ceiling / 2);
      expect(backoffDelay(attempt, 0.999999)).toBeLessThanOrEqual(ceiling);
      expect(backoffDelay(attempt, 0.999999)).toBeGreaterThan(ceiling * 0.99);
    });
    expect(backoffDelay(50, 0.999999)).toBeLessThanOrEqual(MOST_WAIT);
  });

  it("reconnects after a drop with a new ticket, waiting no less than the first wait", async () => {
    const { realtime, sockets, ticket, last } = harness();
    realtime.start();
    await settle();
    last().open();
    last().shut(1006);

    await vi.advanceTimersByTimeAsync(FIRST_WAIT - 10);
    expect(sockets).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(10);

    expect(sockets).toHaveLength(2);
    expect(ticket).toHaveBeenCalledTimes(2);
    realtime.stop();
  });

  it("keeps backing off when the server closes each socket at once", async () => {
    const { realtime, sockets, last } = harness();
    realtime.start();
    await settle();
    const waits: number[] = [];
    for (let n = 0; n < 6; n += 1) {
      last().open();
      last().shut(CLOSE.noTicket);
      const before = sockets.length;
      let waited = 0;
      while (sockets.length === before) {
        await vi.advanceTimersByTimeAsync(100);
        waited += 100;
      }
      waits.push(waited);
    }

    expect(waits).toEqual([1, 2, 4, 8, 16, 30].map((s) => s * SECOND));
    realtime.stop();
  });

  it("starts the count again once a socket has stayed open 10 s", async () => {
    const { realtime, sockets, last } = harness();
    realtime.start();
    await settle();
    last().shut(1006);
    await vi.advanceTimersByTimeAsync(FIRST_WAIT);
    last().shut(1006);
    await vi.advanceTimersByTimeAsync(2 * SECOND);
    last().open();
    await vi.advanceTimersByTimeAsync(10 * SECOND);
    last().shut(1006);
    const before = sockets.length;

    await vi.advanceTimersByTimeAsync(FIRST_WAIT);

    expect(sockets).toHaveLength(before + 1);
    realtime.stop();
  });

  it("backs off when no ticket comes (a blip, too many asked)", async () => {
    const { realtime, ticket } = harness();
    ticket.mockRejectedValueOnce(new Error("RATE_LIMITED"));
    realtime.start();
    await settle();
    expect(ticket).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(FIRST_WAIT);

    expect(ticket).toHaveBeenCalledTimes(2);
    realtime.stop();
  });
});

describe("closes that end it", () => {
  it.each([
    ["revoked sessions", CLOSE.revoked],
    ["another origin", CLOSE.forbidden],
  ])("never reconnects after %s", async (_, code) => {
    const { realtime, sockets, last } = harness();
    realtime.start();
    await settle();
    last().open();
    last().shut(code);

    await vi.advanceTimersByTimeAsync(10 * MOST_WAIT);

    expect(sockets).toHaveLength(1);
    expect(realtime.state).toBe("stopped");
  });

  it.each([
    ["no live ticket", CLOSE.noTicket],
    ["silent 60 s", CLOSE.idle],
    ["too slow", CLOSE.tooSlow],
    ["a dropped network", 1006],
  ])("reconnects after %s", async (_, code) => {
    const { realtime, sockets, last } = harness();
    realtime.start();
    await settle();
    last().open();
    last().shut(code);

    await vi.advanceTimersByTimeAsync(FIRST_WAIT);

    expect(sockets).toHaveLength(2);
    realtime.stop();
  });
});

describe("ping and pong", () => {
  it("pings every 25 s and gives the socket up when no pong comes in 10 s", async () => {
    const { realtime, sockets, last } = harness();
    realtime.start();
    await settle();
    const first = last();
    first.open();

    await vi.advanceTimersByTimeAsync(PING);
    expect(first.sent).toEqual([
      { type: "ping", id: expect.any(String), data: {} },
    ]);
    first.say("pong");
    await vi.advanceTimersByTimeAsync(PING);
    expect(first.closedWith).toBeNull();

    await vi.advanceTimersByTimeAsync(PONG);
    expect(first.closedWith).toBe(1000);
    await vi.advanceTimersByTimeAsync(FIRST_WAIT);
    expect(sockets).toHaveLength(2);
    realtime.stop();
  });
});

describe("a hidden tab", () => {
  it("closes after 5 minutes hidden, and opens again the moment it is shown", async () => {
    const { realtime, sockets, page, last, onReconnect } = harness();
    realtime.start();
    await settle();
    last().open();

    // Answered pings, so the only close is the pause's.
    const answer = setInterval(() => last().say("pong"), SECOND);
    page.set("hidden");
    await vi.advanceTimersByTimeAsync(HIDDEN - 10);
    expect(last().closedWith).toBeNull();
    await vi.advanceTimersByTimeAsync(10);
    clearInterval(answer);
    expect(last().closedWith).toBe(1000);
    expect(realtime.state).toBe("paused");
    await vi.advanceTimersByTimeAsync(10 * MOST_WAIT);
    expect(sockets).toHaveLength(1);

    page.set("visible");
    await settle();
    expect(sockets).toHaveLength(2);
    last().open();
    expect(onReconnect).toHaveBeenCalledTimes(1);
    realtime.stop();
  });

  it("stays connected when shown again within 5 minutes", async () => {
    const { realtime, sockets, page, last } = harness();
    realtime.start();
    await settle();
    last().open();

    const answer = setInterval(() => last().say("pong"), SECOND);
    page.set("hidden");
    await vi.advanceTimersByTimeAsync(HIDDEN - SECOND);
    page.set("visible");
    await vi.advanceTimersByTimeAsync(HIDDEN);
    clearInterval(answer);

    expect(last().closedWith).toBeNull();
    expect(sockets).toHaveLength(1);
    realtime.stop();
  });
});

describe("events", () => {
  it("hands each server event over, and asks again only after a reconnect", async () => {
    const { realtime, events, onReconnect, last } = harness();
    realtime.start();
    await settle();
    last().open();
    expect(onReconnect).not.toHaveBeenCalled();
    last().say("wallet.updated", { balance: 12 });
    expect(events).toEqual([
      { type: "wallet.updated", id: "e1", data: { balance: 12 } },
    ]);

    last().shut(1006);
    await vi.advanceTimersByTimeAsync(FIRST_WAIT);
    last().open();

    expect(onReconnect).toHaveBeenCalledTimes(1);
    realtime.stop();
  });

  it("drops anything that isn't an envelope", () => {
    expect(parseEvent("not json")).toBeNull();
    expect(parseEvent(JSON.stringify({ type: "x" }))).toBeNull();
    expect(parseEvent(JSON.stringify(["typing"]))).toBeNull();
    expect(parseEvent(new ArrayBuffer(2))).toBeNull();
    expect(
      parseEvent(JSON.stringify({ type: "typing", id: "1", data: {} })),
    ).toEqual({ type: "typing", id: "1", data: {} });
  });

  it("says typing at most once a Thread every 3 s, and only while open", async () => {
    const { realtime, last } = harness();
    realtime.start();
    await settle();
    realtime.typing("t1", 0);
    expect(last().sent).toEqual([]);
    last().open();

    realtime.typing("t1", 1_000);
    realtime.typing("t1", 3_999);
    realtime.typing("t2", 3_999);
    realtime.typing("t1", 4_000);

    expect(last().sent).toEqual([
      { type: "typing", id: expect.any(String), data: { thread_id: "t1" } },
      { type: "typing", id: expect.any(String), data: { thread_id: "t2" } },
      { type: "typing", id: expect.any(String), data: { thread_id: "t1" } },
    ]);
    realtime.stop();
  });

  it("closes the socket and stops for good when stopped", async () => {
    const { realtime, sockets, last } = harness();
    realtime.start();
    await settle();
    last().open();

    realtime.stop();
    await vi.advanceTimersByTimeAsync(10 * MOST_WAIT);

    expect(last().closedWith).toBe(1000);
    expect(sockets).toHaveLength(1);
  });
});
