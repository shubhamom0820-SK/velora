import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import type { RealtimeEvent } from "@/lib/ws";
import { z } from "@/lib/zod-mini";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";
import type { Message } from "./messages";

type MessagePage = components["schemas"]["MessagePage"];
type Gender = components["schemas"]["Me"]["gender"];

/**
 * How long the other person's dots stay after their last `typing`: the server
 * relays one every 3 s at most (D-670), so two missed mean they stopped.
 */
export const TYPING_SHOWN_MS = 6_000;

const ThreadEvent = z.object({ thread_id: z.string() });
const MessageNew = z.object({
  thread_id: z.string(),
  message: z.object({
    id: z.string(),
    thread_id: z.string(),
    mine: z.boolean(),
    created_at: z.string(),
  }),
});
const MessageRead = z.object({
  thread_id: z.string(),
  up_to_message_id: z.string(),
  read_at: z.string(),
});
const WalletUpdated = z.object({ balance: z.int() });
const AlbumDecided = z.object({ user_id: z.string() });

const typingTimers = new Map<string, ReturnType<typeof setTimeout>>();

function setTyping(client: QueryClient, threadId: string, on: boolean) {
  clearTimeout(typingTimers.get(threadId));
  typingTimers.delete(threadId);
  client.setQueryData(queryKeys.typing(threadId), on);
  if (on) {
    typingTimers.set(
      threadId,
      setTimeout(() => setTyping(client, threadId, false), TYPING_SHOWN_MS),
    );
  }
}

/** Marks every list of chats stale and asks again those on screen. */
function lists(client: QueryClient) {
  void client.invalidateQueries({ queryKey: [...queryKeys.threads(), "list"] });
}

/** One Thread's screen asked again: its status, its hour, what it costs. */
function thread(client: QueryClient, threadId: string) {
  void client.invalidateQueries({ queryKey: queryKeys.thread(threadId) });
}

/** The in-app list, for an event the API also wrote a notification for. */
function notifications(client: QueryClient) {
  void client.invalidateQueries({
    queryKey: queryKeys.notifications(),
    exact: true,
  });
}

/** A new message at the front of its Thread's newest page, once. */
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

/** "Seen" on each of mine up to the one they read, as the API marks them. */
function markRead(
  client: QueryClient,
  threadId: string,
  upTo: string,
  readAt: string,
) {
  client.setQueryData<InfiniteData<MessagePage>>(
    queryKeys.messages(threadId),
    (data) => {
      if (!data) return data;
      const items = data.pages.flatMap((page) => page.items);
      const target = items.find((item) => item.id === upTo);
      if (!target) return data;
      const until = Date.parse(target.created_at);
      return {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.map((item) =>
            item.mine &&
            item.read_at === null &&
            Date.parse(item.created_at) <= until
              ? { ...item, read_at: readAt }
              : item,
          ),
        })),
      };
    },
  );
}

/**
 * What one event from the socket does to the caches (T-7.12, D-881). A change
 * to a Thread's state (opened, its hour, a knot) is never written from the
 * event: the Thread is asked of the API again, which sends her `expires_at`
 * as null (D-554). Its hour's events are read only by a man, an allowlist
 * like the conversation's (P-460): while `gender` is unknown, nobody's.
 */
export function applyEvent(
  client: QueryClient,
  event: RealtimeEvent,
  gender: Gender | undefined,
): void {
  const { data } = event;
  switch (event.type) {
    case "message.new": {
      const parsed = MessageNew.safeParse(data);
      if (!parsed.success) return;
      // The API's own view of it for me: masked, locked or not (T-7.3).
      const message = data.message as Message;
      addMessage(client, message);
      if (!message.mine) setTyping(client, message.thread_id, false);
      lists(client);
      return;
    }
    case "message.read": {
      const parsed = MessageRead.safeParse(data);
      if (!parsed.success) return;
      const { thread_id, up_to_message_id, read_at } = parsed.data;
      markRead(client, thread_id, up_to_message_id, read_at);
      return;
    }
    case "typing": {
      const parsed = ThreadEvent.safeParse(data);
      if (parsed.success) setTyping(client, parsed.data.thread_id, true);
      return;
    }
    case "thread.expiring":
    case "thread.expired": {
      if (gender !== "male") return;
      const parsed = ThreadEvent.safeParse(data);
      if (!parsed.success) return;
      thread(client, parsed.data.thread_id);
      lists(client);
      if (event.type === "thread.expiring") notifications(client);
      return;
    }
    case "thread.opened":
    case "knot.requested":
    case "knot.accepted":
    case "knot.untied": {
      const parsed = ThreadEvent.safeParse(data);
      if (!parsed.success) return;
      thread(client, parsed.data.thread_id);
      lists(client);
      if (event.type !== "knot.untied") notifications(client);
      return;
    }
    case "wallet.updated": {
      const parsed = WalletUpdated.safeParse(data);
      if (!parsed.success) return;
      client.setQueryData(queryKeys.wallet(), { balance: parsed.data.balance });
      void client.invalidateQueries({ queryKey: queryKeys.walletLedger() });
      return;
    }
    case "match.created":
      void client.invalidateQueries({ queryKey: queryKeys.likes() });
      notifications(client);
      return;
    case "album.decided": {
      const parsed = AlbumDecided.safeParse(data);
      if (!parsed.success) return;
      void client.invalidateQueries({
        queryKey: queryKeys.album(parsed.data.user_id),
      });
      notifications(client);
      return;
    }
    case "gift.received":
      void client.invalidateQueries({ queryKey: queryKeys.gifts() });
      notifications(client);
      return;
    default:
      // A type this build doesn't know: a newer API's, ignored.
      return;
  }
}

/**
 * After a reconnect: whatever happened while the socket was down. Every
 * Thread query on screen (the open one, its messages, the lists) and the
 * wallet are asked again; the rest are marked stale.
 */
export function afterReconnect(client: QueryClient): void {
  void client.invalidateQueries({ queryKey: queryKeys.threads() });
  void client.invalidateQueries({ queryKey: queryKeys.wallet() });
  notifications(client);
}
