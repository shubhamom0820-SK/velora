import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import type { Message } from "@/lib/queries/messages";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import type { ThreadView } from "@/lib/queries/threads";
import {
  envelope,
  fakeApi,
  json,
  type Call,
  type Route,
} from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";
import * as recorder from "@/lib/voice-recorder";
import * as ws from "@/lib/ws";

import { ConversationScreen } from "./ConversationScreen";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: nav.push,
    replace: nav.replace,
    prefetch: vi.fn(),
  }),
  usePathname: () => "/chats/t1",
}));
vi.mock("@/lib/ws", async (original) => ({
  ...(await original<typeof import("@/lib/ws")>()),
  sendTyping: vi.fn(),
}));
vi.mock("@/lib/voice-recorder", async (original) => ({
  ...(await original<typeof import("@/lib/voice-recorder")>()),
  startRecording: vi.fn(),
}));

const ID = "t1";
const MINUTE = 60_000;
const inMinutes = (minutes: number) =>
  new Date(Date.now() + minutes * MINUTE).toISOString();
const PRICES = {
  thread_open: 5,
  thread_reopen: 2,
  thread_extend: 10,
  voice_unlock: 5,
  dm_message: 2,
};
const COUNTDOWN = /\d+[hm] left/;

function thread(overrides: Partial<ThreadView> = {}): ThreadView {
  return {
    id: ID,
    origin: "match",
    status: "active",
    other_user_id: "u2",
    expires_at: null,
    knotted_at: null,
    i_tied: false,
    last_message_at: null,
    created_at: inMinutes(-90),
    other: {
      id: "u2",
      first_name: "Priya",
      username: "priya",
      main_photo_url: null,
      shows_badge: false,
      is_online: true,
      deleted: false,
    },
    send_price: 0,
    can_gift: false,
    kudos: "too_early",
    ...overrides,
  };
}

let sequence = 0;
function message(overrides: Partial<Message> = {}): Message {
  sequence += 1;
  return {
    id: `m${sequence}`,
    thread_id: ID,
    kind: "text",
    body: `Message ${sequence}`,
    masked: false,
    duration_s: null,
    mine: false,
    from_deleted_account: false,
    locked: false,
    read_at: null,
    created_at: inMinutes(-30 + sequence),
    client_msg_id: null,
    ...overrides,
  };
}

/** The screen's API: the Thread, its messages (oldest first), the prices. */
function api(
  view: ThreadView,
  messages: Message[] = [],
  overrides: Record<string, Route> = {},
) {
  return fakeApi({
    [`GET /v1/threads/${ID}`]: () => json(200, view),
    [`GET /v1/threads/${ID}/messages`]: () =>
      json(200, { items: [...messages].reverse(), next_cursor: null }),
    "GET /v1/prices": () => json(200, PRICES),
    [`POST /v1/threads/${ID}/read`]: () => new Response(null, { status: 204 }),
    ...overrides,
  });
}

function renderScreen(gender: "male" | "female" | null) {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  if (gender) {
    client.setQueryData(queryKeys.me(), {
      id: "me",
      gender,
      profile: { first_name: gender === "male" ? "Arjun" : "Priya" },
    });
  }
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConversationScreen id={ID} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

const loaded = () => screen.findByRole("heading", { level: 1 });
const composer = () =>
  screen.getByRole("textbox", { name: t("conversation.placeholder") });
const sends = (calls: Call[]) =>
  calls.filter(
    (call) =>
      call.method === "POST" && call.path === `/v1/threads/${ID}/messages`,
  );
const text = () => document.body.textContent ?? "";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
  nav.push.mockReset();
  nav.replace.mockReset();
  vi.mocked(ws.sendTyping).mockReset();
  vi.mocked(recorder.startRecording).mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("her side says nothing about time or money (D-097, D-554, P-460)", () => {
  it("draws no countdown, no bar, no Extend and no price, whatever expires_at she is sent", async () => {
    api(thread({ expires_at: inMinutes(8) }), [message()]);
    renderScreen("female");
    await loaded();
    await screen.findByText("Message 1");

    expect(text()).not.toMatch(COUNTDOWN);
    expect(text()).not.toMatch(/Vela|hour|Extend|Re-open|Ran out/);
    expect(screen.getByTestId("thread-bar").dataset.share).toBe("0");
    expect(screen.getByText(t("conversation.knotBarHers"))).toBeInTheDocument();
  });

  it("shows her no expired state on an expired Thread, and her message still goes, free", async () => {
    const calls = api(
      thread({ status: "expired", expires_at: inMinutes(-5) }),
      [message({ created_at: inMinutes(-80) })],
      {
        [`POST /v1/threads/${ID}/messages`]: (call) =>
          json(
            200,
            message({
              mine: true,
              body: "Still here",
              client_msg_id: (call.body as { client_msg_id: string })
                .client_msg_id,
            }),
          ),
      },
    );
    renderScreen("female");
    await loaded();
    await screen.findByText(/Message/);

    expect(text()).not.toMatch(/ran out|Re-open|Vela/i);
    await userEvent.type(composer(), "Still here{Enter}");

    await waitFor(() => expect(sends(calls.calls)).toHaveLength(1));
    expect(sends(calls.calls)[0]?.body).toMatchObject({
      kind: "text",
      body: "Still here",
      shown_price: 0,
    });
  });

  it("gives her the mic, and never asks her for prices", async () => {
    const calls = api(thread());
    renderScreen("female");
    await loaded();

    expect(
      screen.getByRole("button", { name: t("conversation.voice.record") }),
    ).toBeInTheDocument();
    expect(calls.sent()).not.toContain("GET /v1/prices");
  });

  it("shows nobody a countdown while who they are loads", async () => {
    api(thread({ expires_at: inMinutes(30) }));
    renderScreen(null);
    await loaded();

    expect(text()).not.toMatch(COUNTDOWN);
    expect(
      screen.queryByRole("button", { name: /Extend/ }),
    ).not.toBeInTheDocument();
  });
});

describe("his Thread (08-DESIGN §8)", () => {
  it("shows the hour left, the bar, and Extend at /prices' price, sending exactly it with the tap's key", async () => {
    const calls = api(thread({ expires_at: inMinutes(41) }), [], {
      [`POST /v1/threads/${ID}/extend`]: () => json(200, thread()),
    });
    renderScreen("male");
    await loaded();

    expect(await screen.findByText("41m left")).toBeInTheDocument();
    expect(text()).toContain(t("conversation.restarts"));
    expect(Number(screen.getByTestId("thread-bar").dataset.share)).toBeCloseTo(
      41 / 60,
      1,
    );
    expect(
      screen.queryByRole("button", { name: t("conversation.voice.record") }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Extend by a day, for 10 Velas",
      }),
    );

    await waitFor(() =>
      expect(calls.sent()).toContain(`POST /v1/threads/${ID}/extend`),
    );
    const extend = calls.calls.find((call) => call.path.endsWith("/extend"));
    expect(extend?.body).toEqual({ shown_price: 10 });
    expect(extend?.headers.get("Idempotency-Key")).toMatch(/^[\w-]{8,64}$/);
  });

  it("offers no Extend on a private message, which never runs out", async () => {
    api(thread({ origin: "dm", expires_at: null, send_price: 2 }));
    renderScreen("male");
    await loaded();

    expect(
      screen.queryByRole("button", { name: /Extend/ }),
    ).not.toBeInTheDocument();
    expect(text()).not.toMatch(COUNTDOWN);
  });

  it("shows his message's price before he sends it, and sends exactly it (D-870)", async () => {
    const calls = api(thread({ origin: "dm", send_price: 2 }), [message()], {
      [`POST /v1/threads/${ID}/messages`]: () =>
        json(200, message({ mine: true })),
    });
    renderScreen("male");
    await loaded();

    expect(
      await screen.findByText("Each message here costs 2 Velas."),
    ).toBeInTheDocument();
    await userEvent.type(composer(), "Hello");
    await userEvent.click(
      screen.getByRole("button", { name: "Send, for 2 Velas" }),
    );

    await waitFor(() => expect(sends(calls.calls)).toHaveLength(1));
    expect(sends(calls.calls)[0]?.body).toMatchObject({ shown_price: 2 });
  });

  it("names no price when his message is free", async () => {
    api(thread({ expires_at: inMinutes(30) }));
    renderScreen("male");
    await loaded();

    expect(
      screen.getByRole("button", { name: t("conversation.send") }),
    ).toBeInTheDocument();
    expect(text()).not.toMatch(/costs/);
  });
});

describe("his expired Thread (D-097, D-253)", () => {
  it("keeps everything readable, marks where the hour ran out and her new message, and re-opens at the price shown", async () => {
    const ranOut = inMinutes(-20);
    const calls = api(
      thread({ status: "expired", expires_at: ranOut }),
      [
        message({ body: "Before", created_at: inMinutes(-90) }),
        message({ body: "After", created_at: inMinutes(-5) }),
      ],
      {
        [`POST /v1/threads/${ID}/reopen`]: () => json(200, thread()),
        [`POST /v1/threads/${ID}/extend`]: () => json(200, thread()),
      },
    );
    renderScreen("male");
    await loaded();

    expect(await screen.findByText("Before")).toBeInTheDocument();
    expect(screen.getByText("After")).toBeInTheDocument();
    expect(screen.getAllByText(t("conversation.ranOutDivider"))).toHaveLength(
      1,
    );
    expect(screen.getByText(/^New · /)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: t("conversation.expired.titleWrote"),
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();

    await userEvent.click(
      await screen.findByRole("button", { name: "Re-open · 2 Velas" }),
    );
    await waitFor(() =>
      expect(calls.sent()).toContain(`POST /v1/threads/${ID}/reopen`),
    );
    await userEvent.click(
      screen.getByRole("button", {
        name: "Re-open and keep it for 24h · 10 Velas",
      }),
    );
    await waitFor(() =>
      expect(calls.sent()).toContain(`POST /v1/threads/${ID}/extend`),
    );
    const bodies = calls.calls
      .filter(
        (call) => call.method === "POST" && /reopen|extend/.test(call.path),
      )
      .map((call) => [call.path.split("/").pop(), call.body]);
    expect(bodies).toEqual([
      ["reopen", { shown_price: 2 }],
      ["extend", { shown_price: 10 }],
    ]);
  });

  it("says the hour ran out, not that she wrote back, when she hasn't", async () => {
    api(thread({ status: "active", expires_at: inMinutes(-1) }), [
      message({ created_at: inMinutes(-90) }),
    ]);
    renderScreen("male");
    await loaded();

    expect(
      await screen.findByRole("heading", {
        name: t("conversation.expired.title"),
      }),
    ).toBeInTheDocument();
    expect(text()).not.toContain(t("conversation.expired.titleWrote"));
    expect(
      screen.getByRole("button", { name: t("conversation.tie") }),
    ).toBeInTheDocument();
  });

  it("asks for a new price when it changed, charging nothing (P-56)", async () => {
    api(thread({ status: "expired", expires_at: inMinutes(-1) }), [], {
      [`POST /v1/threads/${ID}/reopen`]: () =>
        envelope(409, "PRICE_CHANGED", { price: 3 }),
    });
    renderScreen("male");
    await loaded();

    await userEvent.click(
      await screen.findByRole("button", { name: "Re-open · 2 Velas" }),
    );

    expect(
      await screen.findByText("The price changed. It's 3 Velas now."),
    ).toBeInTheDocument();
  });
});

describe("the composer", () => {
  it("sends on Enter, never on Shift+Enter or while an input method composes", async () => {
    const calls = api(thread(), [message()], {
      [`POST /v1/threads/${ID}/messages`]: () =>
        json(200, message({ mine: true })),
    });
    renderScreen("female");
    await loaded();

    await userEvent.type(composer(), "Line one{Shift>}{Enter}{/Shift}two");
    expect(composer()).toHaveValue("Line one\ntwo");
    act(() => {
      composer().dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Enter",
          bubbles: true,
          isComposing: true,
        }),
      );
    });
    // Nothing sent: the draft is still there, and nothing went out.
    expect(composer()).toHaveValue("Line one\ntwo");
    expect(
      screen.queryByText(t("conversation.sending")),
    ).not.toBeInTheDocument();
    expect(sends(calls.calls)).toHaveLength(0);

    await userEvent.type(composer(), "{Enter}");
    await waitFor(() => expect(sends(calls.calls)).toHaveLength(1));
    expect(sends(calls.calls)[0]?.body).toMatchObject({
      body: "Line one\ntwo",
    });
  });

  it("shows a message at once, then the API's copy of it", async () => {
    let answer: (response: Response) => void = () => {};
    api(thread(), [message()], {
      [`POST /v1/threads/${ID}/messages`]: () =>
        new Promise<Response>((resolve) => {
          answer = resolve;
        }),
    });
    renderScreen("female");
    await loaded();

    await userEvent.type(composer(), "Hi there{Enter}");

    expect(await screen.findByText("Hi there")).toBeInTheDocument();
    expect(screen.getByText(t("conversation.sending"))).toBeInTheDocument();
    expect(composer()).toHaveValue("");
    act(() =>
      answer(
        json(
          200,
          message({ mine: true, body: "Hi there", client_msg_id: "x" }),
        ),
      ),
    );
    await waitFor(() =>
      expect(
        screen.queryByText(t("conversation.sending")),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getAllByText("Hi there")).toHaveLength(1);
  });

  it("keeps a failed message with Retry, which sends the same client id", async () => {
    let fail = true;
    const calls = api(thread(), [message()], {
      [`POST /v1/threads/${ID}/messages`]: (call) => {
        if (fail) throw new TypeError("Failed to fetch");
        const { client_msg_id } = call.body as { client_msg_id: string };
        return json(200, message({ mine: true, body: "Again", client_msg_id }));
      },
    });
    renderScreen("female");
    await loaded();

    await userEvent.type(composer(), "Again{Enter}");
    const retry = await screen.findByRole("button", {
      name: t("conversation.retry"),
    });
    expect(screen.getByText(t("conversation.notSent"))).toBeInTheDocument();
    fail = false;
    await userEvent.click(retry);

    await waitFor(() =>
      expect(
        screen.queryByText(t("conversation.notSent")),
      ).not.toBeInTheDocument(),
    );
    const ids = sends(calls.calls).map(
      (call) => (call.body as { client_msg_id: string }).client_msg_id,
    );
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBe(ids[1]);
    expect(screen.getAllByText("Again")).toHaveLength(1);
  });

  it.each([
    ["abuse", t("conversation.rejected.abuse")],
    ["solicitation", t("conversation.rejected.solicitation")],
    ["something_new", t("conversation.rejected.other")],
  ])(
    "explains a message refused for %s and keeps its text in the composer",
    async (rule, words) => {
      api(thread(), [message()], {
        [`POST /v1/threads/${ID}/messages`]: () =>
          envelope(422, "MESSAGE_REJECTED", { rule }),
      });
      renderScreen("female");
      await loaded();

      await userEvent.type(composer(), "paytm kar do{Enter}");

      expect(await screen.findByText(words)).toHaveAttribute("role", "status");
      expect(composer()).toHaveValue("paytm kar do");
      expect(
        screen.queryByText(t("conversation.notSent")),
      ).not.toBeInTheDocument();
    },
  );

  it.each([
    ["THREAD_EXPIRED", 410, t("conversation.expiredRefused")],
    ["ACCOUNT_DELETED", 410, t("conversation.accountDeleted")],
    ["RATE_LIMITED", 429, t("conversation.rateLimited")],
  ])("says what %s means and keeps the text", async (code, status, words) => {
    api(thread({ expires_at: inMinutes(30) }), [message()], {
      [`POST /v1/threads/${ID}/messages`]: () =>
        envelope(status, code, { retry_after_s: 30 }),
    });
    renderScreen("male");
    await loaded();

    await userEvent.type(composer(), "Hello{Enter}");

    expect(await screen.findByText(words)).toHaveAttribute("role", "status");
    expect(composer()).toHaveValue("Hello");
  });

  it("puts his message back with the new price when it changed (P-56)", async () => {
    api(thread({ origin: "dm", send_price: 2 }), [message()], {
      [`POST /v1/threads/${ID}/messages`]: () =>
        envelope(409, "PRICE_CHANGED", { price: 3 }),
    });
    renderScreen("male");
    await loaded();

    await userEvent.type(composer(), "Hello{Enter}");

    expect(
      await screen.findByText("The price changed. It's 3 Velas now."),
    ).toHaveAttribute("role", "status");
    expect(composer()).toHaveValue("Hello");
  });
});

describe("reading", () => {
  it("says Seen with the time under my last message, or Not seen yet", async () => {
    api(thread(), [
      message({ mine: true, body: "First", read_at: "2026-10-09T14:19:00Z" }),
      message({ mine: true, body: "Second" }),
    ]);
    renderScreen("female");
    await loaded();

    expect(
      await screen.findByText(t("conversation.notSeen")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Seen /)).not.toBeInTheDocument();
  });

  it("marks their newest message read when it is on screen (T-7.5)", async () => {
    const theirs = message({ body: "Unread" });
    const calls = api(thread(), [message({ read_at: inMinutes(-1) }), theirs]);
    renderScreen("female");
    await loaded();

    await waitFor(() =>
      expect(calls.sent()).toContain(`POST /v1/threads/${ID}/read`),
    );
    const read = calls.calls.find((call) => call.path.endsWith("/read"));
    expect(read?.body).toEqual({ up_to_message_id: theirs.id });
  });

  it("offers icebreakers on an empty Thread, which fill the composer", async () => {
    api(thread());
    renderScreen("female");
    await loaded();

    await userEvent.click(
      await screen.findByRole("button", {
        name: t("conversation.icebreakers.eaten"),
      }),
    );

    expect(composer()).toHaveValue(t("conversation.icebreakers.eaten"));
  });

  it("shows the typing dots when the socket says so (T-7.12)", async () => {
    api(thread(), [message()]);
    const client = renderScreen("female");
    await loaded();
    await screen.findByText(/Message/);

    act(() => client.setQueryData(queryKeys.typing(ID), true));

    expect(await screen.findByText("Priya is typing")).toBeInTheDocument();
  });
});

describe("voice notes (T-7.9)", () => {
  it("shows him a locked note's price and unlocks it at exactly that price", async () => {
    const note = message({
      kind: "voice",
      body: null,
      duration_s: 12,
      locked: true,
    });
    const calls = api(thread({ expires_at: inMinutes(30) }), [note], {
      [`POST /v1/messages/${note.id}/unlock`]: () =>
        json(200, { url: "https://storage.test/v.webm" }),
    });
    renderScreen("male");
    await loaded();

    await userEvent.click(
      await screen.findByRole("button", {
        name: "Unlock this voice note for 5 Velas",
      }),
    );

    await waitFor(() =>
      expect(calls.sent()).toContain(`POST /v1/messages/${note.id}/unlock`),
    );
    expect(
      calls.calls.find((call) => call.path.endsWith("/unlock"))?.body,
    ).toEqual({ shown_price: 5 });
  });

  it("asks for an unlocked note's link to play, and shows its length", async () => {
    const note = message({ kind: "voice", body: null, duration_s: 12 });
    const calls = api(thread(), [note], {
      [`GET /v1/messages/${note.id}/media`]: () =>
        json(200, { url: "https://storage.test/v.webm" }),
    });
    renderScreen("female");
    await loaded();

    expect(await screen.findByText("0:12")).toBeInTheDocument();
    await waitFor(() =>
      expect(calls.sent()).toContain(`GET /v1/messages/${note.id}/media`),
    );
    expect(text()).not.toMatch(/Unlock/);
  });

  it("sends her recording: upload URL, the PUT, then the send with its key", async () => {
    const recording = {
      blob: new Blob(["ogg"], { type: "audio/ogg" }),
      contentType: "audio/ogg" as const,
      durationMs: 4_600,
    };
    vi.mocked(recorder.startRecording).mockResolvedValue({
      stop: () => Promise.resolve(recording),
      cancel: vi.fn(),
    });
    const calls = api(thread(), [message()], {
      "POST /v1/media/voice-upload-url": () =>
        json(200, {
          message_id: "v1",
          media_key: `voice-uploads/${ID}/v1.ogg`,
          put_url: "https://storage.test/up",
          headers: { "Content-Type": "audio/ogg" },
        }),
      [`POST /v1/threads/${ID}/messages`]: () =>
        json(
          200,
          message({ mine: true, kind: "voice", body: null, duration_s: 5 }),
        ),
    });
    fakeXhr((request) => request.respond(200));
    renderScreen("female");
    await loaded();

    const mic = screen.getByRole("button", {
      name: t("conversation.voice.record"),
    });
    await userEvent.click(mic);
    await userEvent.click(
      await screen.findByRole("button", { name: t("conversation.voice.stop") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: t("conversation.voice.send") }),
    );

    await waitFor(() => expect(sends(calls.calls)).toHaveLength(1));
    expect(
      calls.calls.find((call) => call.path === "/v1/media/voice-upload-url")
        ?.body,
    ).toEqual({
      thread_id: ID,
      content_type: "audio/ogg",
    });
    expect(sends(calls.calls)[0]?.body).toMatchObject({
      kind: "voice",
      media_key: `voice-uploads/${ID}/v1.ogg`,
      duration_s: 5,
      shown_price: 0,
    });
  });

  it.each([
    ["AUDIO_TOO_LONG", t("conversation.voice.tooLong")],
    ["AUDIO_TOO_LARGE", t("conversation.voice.tooLarge")],
    ["UNSUPPORTED_AUDIO", t("conversation.voice.unreadable")],
  ])("says what %s means", async (code, words) => {
    vi.mocked(recorder.startRecording).mockResolvedValue({
      stop: () =>
        Promise.resolve({
          blob: new Blob(["x"]),
          contentType: "audio/mp4" as const,
          durationMs: 3_000,
        }),
      cancel: vi.fn(),
    });
    api(thread(), [message()], {
      "POST /v1/media/voice-upload-url": () =>
        json(200, {
          message_id: "v1",
          media_key: "k",
          put_url: "https://storage.test/up",
          headers: {},
        }),
      [`POST /v1/threads/${ID}/messages`]: () => envelope(422, code),
    });
    fakeXhr((request) => request.respond(200));
    renderScreen("female");
    await loaded();

    await userEvent.click(
      screen.getByRole("button", { name: t("conversation.voice.record") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: t("conversation.voice.stop") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: t("conversation.voice.send") }),
    );

    expect(await screen.findByText(words)).toHaveAttribute("role", "status");
  });
});

describe("the knot (T-7.7, P-670)", () => {
  it.each([
    ["male", t("conversation.tied.bodyHis"), true],
    ["female", t("conversation.tied.bodyHers"), false],
  ] as const)(
    "celebrates the second tap for a %s, in their words",
    async (gender, body, footer) => {
      const calls = api(thread({ expires_at: inMinutes(30) }), [message()], {
        [`POST /v1/threads/${ID}/knot`]: () =>
          json(200, thread({ status: "knotted", knotted_at: inMinutes(0) })),
      });
      renderScreen(gender);
      await loaded();

      await userEvent.click(
        await screen.findByRole("button", { name: t("conversation.tie") }),
      );

      const sheet = await screen.findByRole("dialog", {
        name: "You and Priya tied the knot",
      });
      expect(within(sheet).getByText(body)).toBeInTheDocument();
      expect(
        within(sheet).queryByText(t("discover.match.footer")) !== null,
      ).toBe(footer);
      if (gender === "female") {
        expect(sheet.textContent).not.toMatch(/hour|Vela/);
      }
      expect(
        calls.calls.find((call) => call.path.endsWith("/knot"))?.method,
      ).toBe("POST");
      await userEvent.click(
        within(sheet).getByRole("button", {
          name: t("conversation.tied.keepTalking"),
        }),
      );
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    },
  );

  it("waits for them once I've tapped", async () => {
    api(thread({ i_tied: true }));
    renderScreen("female");
    await loaded();

    expect(
      screen.getByText("You tied it. Waiting for Priya."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("conversation.tie") }),
    ).not.toBeInTheDocument();
  });

  it("shows a Knot as permanent: no countdown, no knot bar, its day marked", async () => {
    // Midday, so "10 minutes ago" is today whenever the suite runs: on the real
    // clock it was yesterday for 10 minutes after each midnight (P-856).
    const midday = new Date();
    midday.setHours(12, 0, 0, 0);
    vi.useFakeTimers({ now: midday, toFake: ["Date"] });
    api(
      thread({
        status: "knotted",
        knotted_at: inMinutes(-10),
        expires_at: inMinutes(30),
      }),
      [
        message({ created_at: inMinutes(-20) }),
        message({ created_at: inMinutes(-5) }),
      ],
    );
    renderScreen("male");
    await loaded();

    expect(await screen.findByText(/Knotted today/)).toBeInTheDocument();
    expect(text()).not.toMatch(COUNTDOWN);
    expect(screen.getByTestId("thread-bar").dataset.share).toBe("1");
    expect(
      screen.queryByRole("button", { name: t("conversation.tie") }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/^You tied the knot · /)).toBeInTheDocument();
  });
});

describe("the ⋯ menu", () => {
  it("opens their profile, and clears the chat for me alone, back to the list", async () => {
    const calls = api(thread(), [message()], {
      [`POST /v1/threads/${ID}/clear`]: () =>
        new Response(null, { status: 204 }),
    });
    renderScreen("female");
    await loaded();

    await userEvent.click(
      screen.getByRole("button", { name: t("conversation.more") }),
    );
    const menu = await screen.findByRole("dialog", {
      name: t("conversation.more"),
    });
    expect(
      within(menu).getByRole("link", { name: t("conversation.viewProfile") }),
    ).toHaveAttribute("href", "/people/u2");
    expect(
      within(menu).queryByRole("button", { name: t("conversation.untie") }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      within(menu).getByRole("button", { name: t("conversation.clearChat") }),
    );

    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/chats"));
    expect(calls.sent()).toContain(`POST /v1/threads/${ID}/clear`);
  });

  it("unties a Knot only once asked twice", async () => {
    const calls = api(
      thread({ status: "knotted", knotted_at: inMinutes(-60) }),
      [],
      {
        [`DELETE /v1/threads/${ID}/knot`]: () => json(200, thread()),
      },
    );
    renderScreen("female");
    await loaded();

    await userEvent.click(
      screen.getByRole("button", { name: t("conversation.more") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: t("conversation.untie") }),
    );
    expect(calls.sent()).not.toContain(`DELETE /v1/threads/${ID}/knot`);
    const confirm = await screen.findByRole("dialog", {
      name: t("conversation.untieTitle"),
    });
    await userEvent.click(
      within(confirm).getByRole("button", {
        name: t("conversation.untieConfirm"),
      }),
    );

    await waitFor(() =>
      expect(calls.sent()).toContain(`DELETE /v1/threads/${ID}/knot`),
    );
  });
});

describe("its states", () => {
  it("says a chat that isn't mine, or across a block, isn't available", async () => {
    fakeApi({
      [`GET /v1/threads/${ID}`]: () => envelope(404, "NOT_FOUND"),
    });
    renderScreen("female");

    expect(
      await screen.findByText(t("conversation.notFound")),
    ).toBeInTheDocument();
  });

  it("keeps a deleted account's chat readable, with nothing to send", async () => {
    api(
      thread({
        other: {
          id: "u2",
          first_name: null,
          username: null,
          main_photo_url: null,
          shows_badge: false,
          is_online: false,
          deleted: true,
        },
      }),
      [message({ body: "Old words" })],
    );
    renderScreen("male");
    await loaded();

    expect(await screen.findByText("Old words")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      t("conversation.deletedAccount"),
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByText(t("conversation.accountDeleted")),
    ).toBeInTheDocument();
  });
});

describe("live (T-7.12)", () => {
  it("tells the other person I'm typing as I write something, never for blanks", async () => {
    api(thread(), [message()]);
    renderScreen("female");
    await loaded();

    await userEvent.type(composer(), "   ");
    expect(ws.sendTyping).not.toHaveBeenCalled();
    await userEvent.type(composer(), "Hi");

    expect(ws.sendTyping).toHaveBeenCalledWith(ID);
  });

  it.each(["male", "female"] as const)(
    "shows 'Knot tied' to a %s whose Thread became a Knot while it was open, once",
    async (gender) => {
      api(thread({ i_tied: true, expires_at: inMinutes(30) }), [message()]);
      const client = renderScreen(gender);
      await loaded();
      const knot = thread({ status: "knotted", knotted_at: inMinutes(0) });

      // What the socket's `knot.accepted` leads to: the Thread asked again.
      act(() => client.setQueryData(queryKeys.thread(ID), knot));

      const sheet = await screen.findByRole("dialog", {
        name: "You and Priya tied the knot",
      });
      await userEvent.click(
        within(sheet).getByRole("button", {
          name: t("conversation.tied.keepTalking"),
        }),
      );
      act(() => client.setQueryData(queryKeys.thread(ID), { ...knot }));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    },
  );

  it("opens once for my own tap, when the Thread asked again then shows that same Knot", async () => {
    const knot = thread({ status: "knotted", knotted_at: inMinutes(0) });
    // The Thread asked again after the tap answers only once the sheet is
    // closed: the order in which a second sheet could open.
    let release: () => void = () => {};
    const closed = new Promise<void>((resolve) => {
      release = resolve;
    });
    let tapped = false;
    api(thread({ expires_at: inMinutes(30) }), [message()], {
      [`GET /v1/threads/${ID}`]: async () => {
        if (!tapped) return json(200, thread({ expires_at: inMinutes(30) }));
        await closed;
        return json(200, knot);
      },
      [`POST /v1/threads/${ID}/knot`]: () => {
        tapped = true;
        return json(200, knot);
      },
    });
    const client = renderScreen("male");
    await loaded();
    await userEvent.click(
      await screen.findByRole("button", { name: t("conversation.tie") }),
    );
    const sheet = await screen.findByRole("dialog", {
      name: "You and Priya tied the knot",
    });
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("conversation.tied.keepTalking"),
      }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    release();
    await waitFor(() =>
      expect(
        client.getQueryData<ThreadView>(queryKeys.thread(ID))?.status,
      ).toBe("knotted"),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("never shows 'Knot tied' for a Knot that was already one when the chat opened", async () => {
    api(thread({ status: "knotted", knotted_at: inMinutes(-60) }), [
      message({ body: "Hello" }),
    ]);
    const client = renderScreen("male");
    await loaded();
    await screen.findByText("Hello");

    act(() => {
      void client.invalidateQueries({ queryKey: queryKeys.thread(ID) });
    });

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("his gift button (T-7.12, D-880)", () => {
  it("opens the gift sheet for her where the Thread says a gift is taken", async () => {
    const calls = api(thread({ can_gift: true }), [message()], {
      "GET /v1/gifts": () =>
        json(200, {
          gifts: [{ id: "coffee", label: "Coffee", asset: "☕", credits: 5 }],
          free_sends_left: 3,
          free_sends_reset_at: "2026-10-11T18:30:00Z",
        }),
    });
    renderScreen("male");
    await loaded();

    await userEvent.click(
      screen.getByRole("button", { name: "Send Priya a gift" }),
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await waitFor(() => expect(calls.sent()).toContain("GET /v1/gifts"));
  });

  it.each([
    ["a man", "male", false, false],
    ["a woman", "female", false, false],
    // The browser never reads a gender to decide: the Thread's answer does.
    ["whoever the Thread says", "female", true, true],
  ] as const)("follows can_gift for %s", async (_, gender, canGift, shown) => {
    api(thread({ can_gift: canGift }), [message()]);
    renderScreen(gender);
    await loaded();

    expect(
      screen.queryByRole("button", { name: "Send Priya a gift" }) !== null,
    ).toBe(shown);
  });
});

describe("the kudos prompt (T-7.12, D-790, D-880)", () => {
  const prompt = () =>
    screen.queryByRole("region", {
      name: t("profile.kudosAsk", { name: "Priya" }),
    });

  it.each([
    ["can_give", true],
    ["too_early", false],
    ["given", false],
  ] as const)("is shown for %s: %s", async (kudos, shown) => {
    api(thread({ kudos }), [message({ body: "Hello" })]);
    renderScreen("female");
    await loaded();
    await screen.findByText("Hello");

    expect(prompt() !== null).toBe(shown);
  });

  it("gives kudos once, and asks the Thread again so the prompt goes", async () => {
    const calls = api(thread({ kudos: "can_give" }), [message()], {
      "POST /v1/kudos": () => json(201, { to_id: "u2", kind: "great_chat" }),
    });
    renderScreen("male");
    await loaded();
    const before = calls.sent().filter((c) => c === `GET /v1/threads/${ID}`);

    await userEvent.click(
      within(prompt() as HTMLElement).getAllByRole("button")[0] as HTMLElement,
    );

    await waitFor(() =>
      expect(
        calls.sent().filter((c) => c === `GET /v1/threads/${ID}`).length,
      ).toBeGreaterThan(before.length),
    );
    expect(calls.sent()).toContain("POST /v1/kudos");
  });
});

describe("Report and Block in the ⋯ menu (P-764)", () => {
  async function openMenu() {
    await userEvent.click(
      screen.getByRole("button", { name: t("conversation.more") }),
    );
    return screen.findByRole("dialog", { name: t("conversation.more") });
  }

  it("reports with this Thread as the evidence, and blocks too unless turned off", async () => {
    const calls = api(thread(), [message()], {
      "POST /v1/reports": () => json(201, {}),
    });
    renderScreen("female");
    await loaded();

    await userEvent.click(
      within(await openMenu()).getByRole("button", {
        name: t("profile.report"),
      }),
    );
    const sheet = await screen.findByRole("dialog", {
      name: t("profile.reportTitle", { name: "Priya" }),
    });
    await userEvent.click(
      within(sheet).getAllByRole("radio")[2] as HTMLElement,
    );
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("profile.reportSend") }),
    );

    await waitFor(() => expect(calls.sent()).toContain("POST /v1/reports"));
    const sent = calls.calls.find((c) => c.path === "/v1/reports");
    expect(sent?.body).toMatchObject({
      reported_id: "u2",
      reason: "harass",
      thread_id: ID,
      also_block: true,
    });
  });

  it("blocks silently and leaves the chat, which is gone for both", async () => {
    const calls = api(thread(), [message()], {
      "POST /v1/blocks": () => json(201, { id: "b1" }),
    });
    renderScreen("female");
    await loaded();

    await userEvent.click(
      within(await openMenu()).getByRole("button", {
        name: t("profile.block", { name: "Priya" }),
      }),
    );
    const sheet = await screen.findByRole("dialog", {
      name: t("profile.blockTitle", { name: "Priya" }),
    });
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("profile.block", { name: "Priya" }),
      }),
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/chats"));
    const sent = calls.calls.find((c) => c.path === "/v1/blocks");
    expect(sent?.body).toEqual({ user_id: "u2" });
    expect(
      await screen.findByText(t("profile.blocked", { name: "Priya" })),
    ).toBeInTheDocument();
  });

  it("still reports and blocks a deleted account, which has no profile to open", async () => {
    api(
      thread({
        other: {
          id: "u2",
          first_name: "",
          username: null,
          main_photo_url: null,
          shows_badge: false,
          is_online: false,
          deleted: true,
        },
      }),
      [message()],
    );
    renderScreen("female");
    await loaded();

    const menu = await openMenu();

    expect(
      within(menu).queryByRole("link", { name: t("conversation.viewProfile") }),
    ).toBeNull();
    expect(
      within(menu).getByRole("button", { name: t("profile.report") }),
    ).toBeInTheDocument();
    expect(
      within(menu).getByRole("button", {
        name: t("profile.block", { name: t("conversation.deletedAccount") }),
      }),
    ).toBeInTheDocument();
  });
});
