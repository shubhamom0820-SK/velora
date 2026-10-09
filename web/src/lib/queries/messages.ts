import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import { putToStorage } from "@/lib/upload";
import type { VoiceContentType } from "@/lib/voice-recorder";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type Message = components["schemas"]["Message"];
type MessagePage = components["schemas"]["MessagePage"];

/** A page of messages: the API's largest (`core/pagination`). */
export const MESSAGES_PAGE = 50;

/** A text message is 1 to 2,000 characters, not blank (`POST /messages`). */
export const MESSAGE_MAX = 2000;

/**
 * A voice note's link is signed for 10 minutes (D-027): kept a little less,
 * so a tap never plays a link that has just run out.
 */
const VOICE_LINK_FRESH_MS = 8 * 60_000;

/**
 * A Thread's messages (`GET /threads/{id}/messages`, T-7.3): newest first, a
 * page at a time, after my clearing only (D-006). The screen draws them oldest
 * first and asks for the next page as the reader scrolls back.
 */
export function useMessages(threadId: string, enabled = true) {
  return useInfiniteQuery({
    queryKey: queryKeys.messages(threadId),
    enabled,
    queryFn: ({ pageParam, signal }) =>
      api.get("/v1/threads/{thread_id}/messages", {
        params: { thread_id: threadId },
        query: { cursor: pageParam, limit: MESSAGES_PAGE },
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

/**
 * Puts a sent message at the front of the newest page, once: the send's answer
 * and a refetch may both bring it.
 */
function addMessage(client: QueryClient, message: Message) {
  client.setQueryData<InfiniteData<MessagePage>>(
    queryKeys.messages(message.thread_id),
    (data) => {
      if (!data) return data;
      const known = data.pages.some((page) =>
        page.items.some((item) => item.id === message.id),
      );
      if (known) return data;
      const [first, ...rest] = data.pages;
      return {
        ...data,
        pages: [
          {
            ...(first ?? { next_cursor: null }),
            items: [message, ...(first?.items ?? [])],
          },
          ...rest,
        ],
      };
    },
  );
}

/** After a send: what the next one costs, and the chats list's preview. */
function afterSend(client: QueryClient, threadId: string) {
  void client.invalidateQueries({ queryKey: queryKeys.thread(threadId) });
  void client.invalidateQueries({ queryKey: [...queryKeys.threads(), "list"] });
}

export type SendText = {
  /** Made once per message by the screen, and sent again with its retry. */
  client_msg_id: string;
  body: string;
  /** The price the composer showed, `send_price` (P-56, D-600). */
  shown_price: number;
};

/**
 * Sends a text (`POST /threads/{id}/messages`). The screen shows it at once
 * under its `client_msg_id`; a retry sends the same id, so the API stores it
 * once and charges once. His may spend Velas, so the balance is asked again.
 */
export function useSendMessage(threadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ client_msg_id, body, shown_price }: SendText) =>
      api.post("/v1/threads/{thread_id}/messages", {
        params: { thread_id: threadId },
        body: { client_msg_id, kind: "text", body, shown_price },
      }),
    meta: { touchesWallet: true },
    onSuccess: (message) => addMessage(client, message),
    onSettled: () => afterSend(client, threadId),
  });
}

export type SendVoice = {
  client_msg_id: string;
  blob: Blob;
  contentType: VoiceContentType;
  /** Whole seconds, 1 to 60: checked by the API, never kept (D-620). */
  duration_s: number;
  onProgress?: (percent: number) => void;
};

/**
 * Sends her voice note (T-7.9, D-620): an upload URL for this Thread, the
 * recording PUT there with exactly the headers it was signed with, then the
 * send, which judges and measures the bytes. Hers alone, and free (D-098).
 */
export function useSendVoice(threadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      client_msg_id,
      blob,
      contentType,
      duration_s,
      onProgress,
    }: SendVoice) => {
      const upload = await api.post("/v1/media/voice-upload-url", {
        body: { thread_id: threadId, content_type: contentType },
      });
      await putToStorage(upload.put_url, blob, upload.headers, { onProgress });
      return api.post("/v1/threads/{thread_id}/messages", {
        params: { thread_id: threadId },
        body: {
          client_msg_id,
          kind: "voice",
          media_key: upload.media_key,
          duration_s,
          shown_price: 0,
        },
      });
    },
    onSuccess: (message) => addMessage(client, message),
    onSettled: () => afterSend(client, threadId),
  });
}

/**
 * Marks their messages read up to one (`POST /threads/{id}/read`, T-7.5):
 * they see "Seen" under theirs. Nothing to put back if it fails.
 */
export function useMarkRead(threadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (upToMessageId: string) =>
      api.post("/v1/threads/{thread_id}/read", {
        params: { thread_id: threadId },
        body: { up_to_message_id: upToMessageId },
      }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: [...queryKeys.threads(), "list"],
      });
    },
  });
}

/** Marks one message unlocked wherever the cache holds it. */
function unlocked(client: QueryClient, threadId: string, messageId: string) {
  client.setQueryData<InfiniteData<MessagePage>>(
    queryKeys.messages(threadId),
    (data) =>
      data && {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.map((item) =>
            item.id === messageId ? { ...item, locked: false } : item,
          ),
        })),
      },
  );
}

export type UnlockVoice = {
  threadId: string;
  messageId: string;
  /** The price the locked card said, from `/prices` (P-56, D-600). */
  shown_price: number;
};

/**
 * Unlocks a voice note for him (`POST /messages/{id}/unlock`, T-7.9, D-621):
 * once, at the price the card showed; the answer is the link to play.
 */
export function useUnlockVoice() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, shown_price }: UnlockVoice) =>
      api.post("/v1/messages/{message_id}/unlock", {
        params: { message_id: messageId },
        body: { shown_price },
      }),
    meta: { touchesWallet: true },
    onSuccess: (link, { threadId, messageId }) => {
      client.setQueryData(queryKeys.voiceMedia(messageId), link);
      unlocked(client, threadId, messageId);
    },
  });
}

/**
 * A voice note's link (`GET /messages/{id}/media`), for anyone it isn't
 * locked for. Asked only once someone presses play (`enabled`).
 */
export function useVoiceMedia(messageId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.voiceMedia(messageId),
    enabled,
    staleTime: VOICE_LINK_FRESH_MS,
    gcTime: VOICE_LINK_FRESH_MS,
    queryFn: ({ signal }) =>
      api.get("/v1/messages/{message_id}/media", {
        params: { message_id: messageId },
        signal,
      }),
  });
}

/**
 * Whether the other person is typing. Only the socket writes it (T-7.12);
 * nothing here asks the API, so until then it stays false.
 */
export function useTyping(threadId: string): boolean {
  const query = useQuery({
    queryKey: queryKeys.typing(threadId),
    queryFn: () => false,
    enabled: false,
    initialData: false,
  });
  return query.data;
}
