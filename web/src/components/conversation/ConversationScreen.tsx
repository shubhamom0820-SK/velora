"use client";

import { useQueryClient } from "@tanstack/react-query";
import { MessageCircleOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import { queryKeys } from "@/lib/queries/keys";
import { useMe } from "@/lib/queries/me";
import {
  useMarkRead,
  useMessages,
  useSendMessage,
  useSendVoice,
  useTyping,
} from "@/lib/queries/messages";
import {
  useClearThread,
  useExtendThread,
  useReopenThread,
  useThread,
  useTieKnot,
  useUntieKnot,
} from "@/lib/queries/threads";
import { usePrices } from "@/lib/queries/wallet";
import { useNow } from "@/lib/ticker";
import { durationSeconds, type Recording } from "@/lib/voice-recorder";

import { Composer } from "./Composer";
import { ConversationHeader } from "./ConversationHeader";
import { ConversationMenu } from "./ConversationMenu";
import { ExpiredPanel } from "./ExpiredPanel";
import { KnotBar } from "./KnotBar";
import { KnotTiedSheet } from "./KnotTiedSheet";
import { MessageList, type Pending } from "./MessageList";

/** As the chats list: the next page is asked this far before the top. */
const PREFETCH_MARGIN = "200px";

/** The prototype's icebreakers, three shown on an empty Thread. */
const ICEBREAKERS = [
  "conversation.icebreakers.laugh",
  "conversation.icebreakers.eaten",
  "conversation.icebreakers.truths",
] as const;

/** A refusal's words, by `details.rule` (D-552). */
function rejectedNote(rule: unknown): string {
  if (rule === "abuse") return t("conversation.rejected.abuse");
  if (rule === "solicitation") return t("conversation.rejected.solicitation");
  return t("conversation.rejected.other");
}

const priceChanged = (error: ApiError) =>
  t("conversation.priceChanged", {
    velas: creditsText(Number(error.details?.price)),
  });

/**
 * One conversation (T-7.11, 08-DESIGN §8), at `/chats/[id]`: the header, the
 * messages oldest first with earlier ones as the reader scrolls back, the
 * knot bar, and the composer, or, on his expired Thread, the panel that
 * re-opens it. A message shows at once and is matched to the API's copy by
 * its `client_msg_id`; a failed one keeps Retry, which sends the same id. A
 * refused one comes back to the composer with the reason.
 *
 * **Her side says nothing about time or money** (D-097, D-554, P-460): no
 * countdown, no bar, no Extend, no expired panel, no price, whatever `status`
 * or `expires_at` the API sends. Only a man is shown them, an allowlist: while
 * `me` loads, nobody is. An expired Thread takes her messages, so her composer
 * always works.
 *
 * Every paid button sends the price it showed (P-56, D-600): re-open and
 * Extend from `/prices`, an unlock from `/prices`, his message from the
 * Thread's `send_price` (D-870).
 */
export function ConversationScreen({ id }: { id: string }) {
  const router = useRouter();
  const toast = useToast();
  const client = useQueryClient();
  const me = useMe().data;
  const man = me?.gender === "male";
  const woman = me?.gender === "female";
  const thread = useThread(id);
  const messages = useMessages(id, thread.isSuccess);
  const prices = usePrices({ enabled: man });
  const typing = useTyping(id);
  const now = useNow();

  const send = useSendMessage(id);
  const sendVoice = useSendVoice(id);
  const markRead = useMarkRead(id);
  const tie = useTieKnot();
  const untie = useUntieKnot();
  const reopen = useReopenThread();
  const extend = useExtendThread();
  const clear = useClearThread();

  const [draft, setDraft] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [tiedOpen, setTiedOpen] = useState(false);
  const [buying, setBuying] = useState<"reopen" | "extend" | "tie" | null>(
    null,
  );
  // A recording kept for its Retry; a tap's Idempotency-Key kept for a retry
  // of that tap after no answer came (D-077).
  const recordings = useRef(new Map<string, Recording>());
  const tapKeys = useRef<{ reopen?: string; extend?: string }>({});
  const marked = useRef<string | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const view = thread.data;
  const ordered = useMemo(
    () =>
      (messages.data?.pages.flatMap((page) => page.items) ?? [])
        .slice()
        .reverse(),
    [messages.data],
  );

  // His alone, by the clock or by the API (D-560): her side reads nothing of
  // the hour, whatever it is sent (P-460).
  const hisExpiry =
    man && view && view.status !== "knotted" && view.expires_at
      ? view.expires_at
      : null;
  const expired =
    hisExpiry !== null &&
    (view?.status === "expired" || Date.parse(hisExpiry) <= now);
  const ranOutAt = expired ? hisExpiry : null;
  const sheWrote =
    ranOutAt !== null &&
    ordered.some(
      (message) =>
        !message.mine && Date.parse(message.created_at) > Date.parse(ranOutAt),
    );
  const theirName = view?.other.deleted
    ? t("conversation.deletedAccount")
    : (view?.other.first_name ?? "");
  const extendPrice =
    man &&
    view &&
    view.origin === "match" &&
    view.status === "active" &&
    !expired
      ? prices.data?.thread_extend
      : undefined;

  // Their newest message, read now that it is on screen (T-7.5).
  const newestTheirs = useMemo(
    () => [...ordered].reverse().find((message) => !message.mine),
    [ordered],
  );
  const { mutate: markUpTo } = markRead;
  useEffect(() => {
    if (!newestTheirs || newestTheirs.read_at !== null) return;
    if (marked.current === newestTheirs.id) return;
    marked.current = newestTheirs.id;
    markUpTo(newestTheirs.id);
  }, [newestTheirs, markUpTo]);

  // The newest message in view: on opening, and when one arrives.
  const newestId = ordered.at(-1)?.id;
  useEffect(() => {
    if (newestId === undefined) return;
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [newestId, pending.length]);

  // Earlier messages as the reader scrolls back to the top.
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = messages;
  useEffect(() => {
    const node = top.current;
    if (!node || !hasNextPage || isFetchingNextPage || isFetchNextPageError) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void fetchNextPage();
        }
      },
      { rootMargin: PREFETCH_MARGIN },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage]);

  const drop = useCallback((clientMsgId: string) => {
    recordings.current.delete(clientMsgId);
    setPending((items) =>
      items.filter((item) => item.client_msg_id !== clientMsgId),
    );
  }, []);

  const failed = useCallback((clientMsgId: string) => {
    setPending((items) =>
      items.map((item) =>
        item.client_msg_id === clientMsgId
          ? { ...item, state: "failed" }
          : item,
      ),
    );
  }, []);

  /** A refused text back in the composer, unless something new is there. */
  function restore(body: string) {
    setDraft((current) => (current.trim() === "" ? body : current));
  }

  /**
   * A refusal the composer explains, or false: then it may be retried. Each
   * sends the person somewhere they can act: the reason, the store sheet
   * (QueryProvider), the expired panel, or the new price.
   */
  function explain(error: unknown): boolean {
    if (!(error instanceof ApiError)) return false;
    switch (error.code) {
      case "MESSAGE_REJECTED":
        setNote(rejectedNote(error.details?.rule));
        return true;
      case "THREAD_EXPIRED":
        setNote(t("conversation.expiredRefused"));
        void client.invalidateQueries({ queryKey: queryKeys.thread(id) });
        return true;
      case "ACCOUNT_DELETED":
        setNote(t("conversation.accountDeleted"));
        void client.invalidateQueries({ queryKey: queryKeys.thread(id) });
        return true;
      case "PRICE_CHANGED":
        setNote(priceChanged(error));
        void client.invalidateQueries({ queryKey: queryKeys.thread(id) });
        return true;
      case "INSUFFICIENT_CREDITS":
        return true;
      case "RATE_LIMITED":
        setNote(t("conversation.rateLimited"));
        return true;
      case "UNSUPPORTED_AUDIO":
        setNote(t("conversation.voice.unreadable"));
        return true;
      case "AUDIO_TOO_LARGE":
        setNote(t("conversation.voice.tooLarge"));
        return true;
      case "AUDIO_TOO_LONG":
        setNote(t("conversation.voice.tooLong"));
        return true;
      case "NOT_FOUND":
        void client.invalidateQueries({ queryKey: queryKeys.thread(id) });
        return true;
      default:
        return false;
    }
  }

  async function sendText(body: string, clientMsgId?: string) {
    const client_msg_id = clientMsgId ?? crypto.randomUUID();
    const item: Pending = {
      client_msg_id,
      created_at: new Date().toISOString(),
      state: "sending",
      kind: "text",
      body,
    };
    setPending((items) => [
      ...items.filter((each) => each.client_msg_id !== client_msg_id),
      item,
    ]);
    setDraft("");
    setNote(null);
    try {
      await send.mutateAsync({
        client_msg_id,
        body,
        // Hers is always 0 (D-098); his, what the composer showed.
        shown_price: man ? (view?.send_price ?? 0) : 0,
      });
      drop(client_msg_id);
    } catch (error) {
      if (explain(error)) {
        drop(client_msg_id);
        restore(body);
      } else {
        failed(client_msg_id);
      }
    }
  }

  async function sendRecording(recording: Recording, clientMsgId?: string) {
    const client_msg_id = clientMsgId ?? crypto.randomUUID();
    const seconds = durationSeconds(recording.durationMs);
    recordings.current.set(client_msg_id, recording);
    setPending((items) => [
      ...items.filter((each) => each.client_msg_id !== client_msg_id),
      {
        client_msg_id,
        created_at: new Date().toISOString(),
        state: "sending",
        kind: "voice",
        duration_s: seconds,
        progress: 0,
      },
    ]);
    setNote(null);
    try {
      await sendVoice.mutateAsync({
        client_msg_id,
        blob: recording.blob,
        contentType: recording.contentType,
        duration_s: seconds,
        onProgress: (percent) =>
          setPending((items) =>
            items.map((each) =>
              each.client_msg_id === client_msg_id && each.kind === "voice"
                ? { ...each, progress: percent }
                : each,
            ),
          ),
      });
      drop(client_msg_id);
    } catch (error) {
      if (explain(error)) drop(client_msg_id);
      else failed(client_msg_id);
    }
  }

  function retry(item: Pending) {
    if (item.kind === "text") {
      void sendText(item.body, item.client_msg_id);
      return;
    }
    const recording = recordings.current.get(item.client_msg_id);
    if (recording) void sendRecording(recording, item.client_msg_id);
    else drop(item.client_msg_id);
  }

  async function onTie() {
    setBuying("tie");
    try {
      const result = await tie.mutateAsync(id);
      if (result.status === "knotted") setTiedOpen(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "ACCOUNT_DELETED") {
        setNote(t("conversation.accountDeleted"));
      } else {
        toast.show({ message: t("conversation.tieFailed"), tone: "error" });
      }
    } finally {
      setBuying(null);
    }
  }

  async function buyTime(what: "reopen" | "extend") {
    const price =
      prices.data?.[what === "reopen" ? "thread_reopen" : "thread_extend"];
    if (price === undefined || buying !== null) return;
    const key = (tapKeys.current[what] ??= crypto.randomUUID());
    setBuying(what);
    try {
      await (what === "reopen" ? reopen : extend).mutateAsync({
        thread_id: id,
        shown_price: price,
        key,
      });
      tapKeys.current[what] = undefined;
      if (what === "extend" && !expired) {
        toast.show({ message: t("conversation.extended") });
      }
    } catch (error) {
      if (!(error instanceof ApiError)) {
        // No answer: the same key again, so a retry is charged once.
        toast.show({
          message: t(
            what === "reopen"
              ? "conversation.expired.reopenFailed"
              : "conversation.extendFailed",
          ),
          tone: "error",
        });
        return;
      }
      tapKeys.current[what] = undefined;
      if (error.code === "PRICE_CHANGED") {
        toast.show({ message: priceChanged(error), tone: "error" });
      } else if (error.code !== "INSUFFICIENT_CREDITS") {
        // Out of Velas opens the store sheet instead (QueryProvider).
        toast.show({
          message: t(
            what === "reopen"
              ? "conversation.expired.reopenFailed"
              : "conversation.extendFailed",
          ),
          tone: "error",
        });
      }
    } finally {
      setBuying(null);
    }
  }

  async function onClear() {
    try {
      await clear.mutateAsync(id);
      toast.show({ message: t("conversation.cleared") });
      router.push("/chats");
    } catch {
      toast.show({ message: t("conversation.clearFailed"), tone: "error" });
    }
  }

  async function onUntie(): Promise<boolean> {
    try {
      await untie.mutateAsync(id);
      toast.show({ message: t("conversation.untied") });
      return true;
    } catch {
      toast.show({ message: t("conversation.untieFailed"), tone: "error" });
      return false;
    }
  }

  if (thread.isPending) {
    return (
      <div aria-busy className="flex flex-col gap-4 px-(--shell-gutter) py-4">
        <Skeleton className="h-12" />
        <Skeleton className="w-2/3" />
        <Skeleton className="ml-auto w-1/2" />
        <Skeleton className="w-3/5" />
      </div>
    );
  }
  if (thread.isError || !view) {
    return thread.error instanceof ApiError &&
      thread.error.code === "NOT_FOUND" ? (
      <EmptyState
        icon={MessageCircleOff}
        title={t("conversation.notFound")}
        body={t("conversation.notFoundBody")}
        action={{
          label: t("conversation.back"),
          onClick: () => router.push("/chats"),
        }}
      />
    ) : (
      <ErrorState
        title={t("conversation.failed")}
        onRetry={() => void thread.refetch()}
      />
    );
  }

  const knotted = view.status === "knotted";
  const deleted = view.other.deleted;
  const empty = ordered.length === 0 && pending.length === 0;

  let list;
  if (messages.isPending) {
    list = (
      <div aria-busy className="flex flex-col gap-3">
        <Skeleton className="w-2/3" />
        <Skeleton className="ml-auto w-1/2" />
      </div>
    );
  } else if (messages.isError) {
    list = (
      <ErrorState
        title={t("conversation.failed")}
        onRetry={() => void messages.refetch()}
      />
    );
  } else if (empty && !expired && !deleted) {
    list = (
      <div className="flex flex-col gap-3 py-6">
        <h2 className="text-title-2 text-ink">
          {t("conversation.emptyTitle")}
        </h2>
        <p className="text-small text-mute">{t("conversation.emptyBody")}</p>
        <ul className="flex flex-col gap-2">
          {ICEBREAKERS.map((key) => (
            <li key={key}>
              <button
                type="button"
                onClick={() => setDraft(t(key))}
                className="bg-surface border-line text-ink text-small rounded-card focus-visible:outline-accent w-full border px-3.5 py-2.5 text-left focus-visible:outline-2"
              >
                {t(key)}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  } else {
    list = (
      <MessageList
        messages={ordered}
        pending={pending}
        ranOutAt={ranOutAt}
        knottedAt={knotted ? view.knotted_at : null}
        theirName={theirName}
        typing={typing}
        unlockPrice={man ? prices.data?.voice_unlock : undefined}
        now={now}
        onRetry={retry}
      />
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <ConversationHeader
        thread={view}
        hisExpiry={hisExpiry}
        now={now}
        extendPrice={extendPrice}
        extending={buying === "extend"}
        onExtend={() => void buyTime("extend")}
        menu={
          <ConversationMenu
            profileId={deleted ? null : view.other.id}
            knotted={knotted}
            clearing={clear.isPending}
            untying={untie.isPending}
            onClear={() => void onClear()}
            onUntie={onUntie}
          />
        }
      />
      <section
        aria-label={t("conversation.messages")}
        className="flex-1 px-(--shell-gutter) py-4"
      >
        <div ref={top} />
        {isFetchingNextPage && (
          <div className="text-mute flex justify-center py-2">
            <Spinner label={t("conversation.loadingOlder")} />
          </div>
        )}
        {isFetchNextPageError && (
          <ErrorState
            title={t("conversation.olderFailed")}
            onRetry={() => void fetchNextPage()}
          />
        )}
        {list}
        <div ref={bottom} />
      </section>
      <div className="sticky bottom-(--shell-nav-height) z-[5] md:bottom-0">
        {!knotted && !deleted && !expired && (
          <KnotBar
            man={man}
            iTied={view.i_tied}
            theirName={theirName}
            busy={buying === "tie"}
            onTie={() => void onTie()}
          />
        )}
        {expired ? (
          <ExpiredPanel
            sheWrote={sheWrote}
            reopenPrice={prices.data?.thread_reopen}
            extendPrice={prices.data?.thread_extend}
            busy={buying}
            onReopen={() => void buyTime("reopen")}
            onReopenAndKeep={() => void buyTime("extend")}
            onTie={() => void onTie()}
          />
        ) : deleted ? (
          <p className="bg-bg border-line text-small text-mute border-t px-(--shell-gutter) py-4">
            {t("conversation.accountDeleted")}
          </p>
        ) : (
          <Composer
            draft={draft}
            onDraftChange={setDraft}
            onSend={(text) => void sendText(text)}
            canRecord={woman}
            onSendVoice={(recording) => void sendRecording(recording)}
            price={man ? view.send_price : 0}
            privateMessage={view.origin === "dm"}
            note={note}
            onNote={setNote}
          />
        )}
      </div>
      <KnotTiedSheet
        open={tiedOpen}
        myName={me?.profile.first_name ?? ""}
        theirName={theirName}
        man={man}
        onClose={() => setTiedOpen(false)}
      />
    </div>
  );
}
