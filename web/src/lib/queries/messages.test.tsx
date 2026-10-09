import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";

import { queryKeys } from "./keys";
import {
  useMarkRead,
  useMessages,
  useSendMessage,
  useSendVoice,
  useTyping,
  useUnlockVoice,
  type Message,
} from "./messages";
import { makeQueryClient } from "./QueryProvider";

const THREAD = "7c1d6c3e-0000-4000-8000-000000000001";
const ID = "7c1d6c3e-0000-4000-8000-0000000000aa";
const CLIENT_ID = "7c1d6c3e-0000-4000-8000-0000000000cc";

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: ID,
    thread_id: THREAD,
    kind: "text",
    body: "Hello",
    masked: false,
    duration_s: null,
    mine: true,
    from_deleted_account: false,
    locked: false,
    read_at: null,
    created_at: "2026-10-09T10:00:00Z",
    client_msg_id: CLIENT_ID,
    ...overrides,
  };
}

let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = makeQueryClient();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("useMessages (T-7.3)", () => {
  it("asks a page of 50 at a time, then the next by its cursor", async () => {
    const api = fakeApi({
      [`GET /v1/threads/${THREAD}/messages`]: (call) =>
        json(200, {
          items: [message()],
          next_cursor: call.query.get("cursor") ? null : "older",
        }),
    });
    const { result } = renderHook(() => useMessages(THREAD), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await act(() => result.current.fetchNextPage());

    expect(api.calls.map((call) => call.query.toString())).toEqual([
      "limit=50",
      "cursor=older&limit=50",
    ]);
  });
});

describe("useSendMessage", () => {
  it("sends the client's id and the price it showed, and puts the answer first", async () => {
    const api = fakeApi({
      [`POST /v1/threads/${THREAD}/messages`]: () => json(200, message()),
    });
    client.setQueryData(queryKeys.messages(THREAD), {
      pages: [
        {
          items: [message({ id: "older", client_msg_id: null })],
          next_cursor: null,
        },
      ],
      pageParams: [null],
    });
    const { result } = renderHook(() => useSendMessage(THREAD), { wrapper });

    await act(() =>
      result.current.mutateAsync({
        client_msg_id: CLIENT_ID,
        body: "Hello",
        shown_price: 2,
      }),
    );

    expect(api.calls[0]?.body).toEqual({
      client_msg_id: CLIENT_ID,
      kind: "text",
      body: "Hello",
      shown_price: 2,
    });
    const cached = client.getQueryData<{ pages: { items: Message[] }[] }>(
      queryKeys.messages(THREAD),
    );
    expect(cached?.pages[0]?.items.map((item) => item.id)).toEqual([
      ID,
      "older",
    ]);
  });

  it("asks the Thread again, what the next one costs, and the balance (T-5.5)", async () => {
    fakeApi({
      [`POST /v1/threads/${THREAD}/messages`]: () => json(200, message()),
    });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useSendMessage(THREAD), { wrapper });

    await act(() =>
      result.current.mutateAsync({
        client_msg_id: CLIENT_ID,
        body: "Hi",
        shown_price: 0,
      }),
    );

    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(queryKeys.thread(THREAD));
    expect(keys).toContainEqual(queryKeys.wallet());
  });
});

describe("useSendVoice (T-7.9, D-620)", () => {
  it("asks for an upload URL, PUTs exactly its headers, then sends its key, free", async () => {
    const api = fakeApi({
      "POST /v1/media/voice-upload-url": () =>
        json(200, {
          message_id: ID,
          media_key: `voice-uploads/${THREAD}/${ID}.m4a`,
          put_url:
            "https://storage.test/velora-private/voice-uploads/x.m4a?sig=1",
          headers: { "Content-Type": "audio/mp4" },
        }),
      [`POST /v1/threads/${THREAD}/messages`]: () =>
        json(200, message({ kind: "voice", body: null, duration_s: 5 })),
    });
    const xhr = fakeXhr((request) => {
      request.progress(50, 100);
      request.respond(200);
    });
    const progress = vi.fn();
    const blob = new Blob(["mp4"], { type: "audio/mp4" });
    const { result } = renderHook(() => useSendVoice(THREAD), { wrapper });

    await act(() =>
      result.current.mutateAsync({
        client_msg_id: CLIENT_ID,
        blob,
        contentType: "audio/mp4",
        duration_s: 5,
        onProgress: progress,
      }),
    );

    expect(api.calls[0]?.body).toEqual({
      thread_id: THREAD,
      content_type: "audio/mp4",
    });
    expect(xhr.requests).toHaveLength(1);
    expect(xhr.requests[0]?.method).toBe("PUT");
    expect(xhr.requests[0]?.headers).toEqual({ "Content-Type": "audio/mp4" });
    expect(xhr.requests[0]?.body).toBe(blob);
    expect(progress).toHaveBeenCalledWith(50);
    expect(api.calls[1]?.body).toEqual({
      client_msg_id: CLIENT_ID,
      kind: "voice",
      media_key: `voice-uploads/${THREAD}/${ID}.m4a`,
      duration_s: 5,
      shown_price: 0,
    });
  });

  it("sends nothing when the upload is refused", async () => {
    const api = fakeApi({
      "POST /v1/media/voice-upload-url": () =>
        json(200, {
          message_id: ID,
          media_key: "k",
          put_url: "https://storage.test/x",
          headers: {},
        }),
    });
    fakeXhr((request) => request.respond(403));
    const { result } = renderHook(() => useSendVoice(THREAD), { wrapper });

    await expect(
      result.current.mutateAsync({
        client_msg_id: CLIENT_ID,
        blob: new Blob(["x"]),
        contentType: "audio/webm",
        duration_s: 3,
      }),
    ).rejects.toThrow();
    expect(api.sent()).toEqual(["POST /v1/media/voice-upload-url"]);
  });
});

describe("useUnlockVoice (T-7.9, D-621)", () => {
  it("sends the price the card showed, keeps the link and unlocks the note", async () => {
    const api = fakeApi({
      [`POST /v1/messages/${ID}/unlock`]: () =>
        json(200, { url: "https://storage.test/voice.webm?sig=1" }),
    });
    client.setQueryData(queryKeys.messages(THREAD), {
      pages: [
        {
          items: [message({ kind: "voice", locked: true, mine: false })],
          next_cursor: null,
        },
      ],
      pageParams: [null],
    });
    const { result } = renderHook(() => useUnlockVoice(), { wrapper });

    await act(() =>
      result.current.mutateAsync({
        threadId: THREAD,
        messageId: ID,
        shown_price: 5,
      }),
    );

    expect(api.calls[0]?.body).toEqual({ shown_price: 5 });
    expect(client.getQueryData(queryKeys.voiceMedia(ID))).toEqual({
      url: "https://storage.test/voice.webm?sig=1",
    });
    const cached = client.getQueryData<{ pages: { items: Message[] }[] }>(
      queryKeys.messages(THREAD),
    );
    expect(cached?.pages[0]?.items[0]?.locked).toBe(false);
  });

  it("unlocks nothing at a price he wasn't shown (P-56)", async () => {
    fakeApi({
      [`POST /v1/messages/${ID}/unlock`]: () =>
        envelope(409, "PRICE_CHANGED", { price: 6 }),
    });
    client.setQueryData(queryKeys.messages(THREAD), {
      pages: [
        {
          items: [message({ kind: "voice", locked: true, mine: false })],
          next_cursor: null,
        },
      ],
      pageParams: [null],
    });
    const { result } = renderHook(() => useUnlockVoice(), { wrapper });

    await expect(
      result.current.mutateAsync({
        threadId: THREAD,
        messageId: ID,
        shown_price: 5,
      }),
    ).rejects.toMatchObject({ code: "PRICE_CHANGED" });
    const cached = client.getQueryData<{ pages: { items: Message[] }[] }>(
      queryKeys.messages(THREAD),
    );
    expect(cached?.pages[0]?.items[0]?.locked).toBe(true);
  });
});

describe("useMarkRead (T-7.5)", () => {
  it("marks their messages read up to one", async () => {
    const api = fakeApi({
      [`POST /v1/threads/${THREAD}/read`]: () =>
        new Response(null, { status: 204 }),
    });
    const { result } = renderHook(() => useMarkRead(THREAD), { wrapper });

    await act(() => result.current.mutateAsync(ID));

    expect(api.calls[0]?.body).toEqual({ up_to_message_id: ID });
  });
});

describe("useTyping", () => {
  it("is false until the socket says otherwise, and never asks the API", async () => {
    const api = fakeApi({});
    const { result } = renderHook(() => useTyping(THREAD), { wrapper });

    expect(result.current).toBe(false);
    act(() => client.setQueryData(queryKeys.typing(THREAD), true));
    await waitFor(() => expect(result.current).toBe(true));
    expect(api.calls).toEqual([]);
  });
});
