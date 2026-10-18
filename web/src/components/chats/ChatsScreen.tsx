"use client";

import { Link2, MessageCircle, Search, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { useMe } from "@/lib/queries/me";
import {
  CLEAR_MAX,
  THREADS_Q_MAX,
  useClearThread,
  useClearThreads,
  useRestoreThread,
  useThreads,
  type ThreadFilter,
  type ThreadRow,
  type Tier,
} from "@/lib/queries/threads";
import { useNow } from "@/lib/ticker";

import { ChatRow } from "./ChatRow";
import { ChatsTabs, type TabCount } from "./ChatsTabs";

/** As the wallet's history: the next page is asked this far before the end. */
const PREFETCH_MARGIN = "200px";
/** A search waits for typing to pause before it asks. */
const SEARCH_DEBOUNCE_MS = 300;
/** How long Undo stays offered after a clearing (T-7.10: "5 s undo toast"). */
const UNDO_MS = 5000;

const FILTERS: [ThreadFilter, Parameters<typeof t>[0]][] = [
  ["all", "chats.filterAll"],
  ["unread", "chats.filterUnread"],
  ["recent", "chats.filterRecent"],
];

function countOf(
  pages: { items: ThreadRow[]; next_cursor: string | null }[] | undefined,
): TabCount {
  const first = pages?.[0];
  return (
    first && { count: first.items.length, more: first.next_cursor !== null }
  );
}

/** His Threads in the list whose time has run out, by the clock (D-560). */
function ranOut(rows: ThreadRow[], now: number): number {
  return rows.filter(
    (row) =>
      row.status !== "knotted" &&
      row.expires_at !== null &&
      Date.parse(row.expires_at) <= now,
  ).length;
}

/**
 * The chats list (T-7.10, 08-DESIGN §8): Threads and Knots, each with its
 * count; the Knots' filters; a search by name; select mode and a bulk clear;
 * "Clear expired (n)"; a clear per row with 5 s to undo it; unread dots.
 *
 * **Her list says nothing about time** (D-097, D-554, P-460): no countdown, no
 * expired state, no "Clear expired", no footer. Only a man is shown them, an
 * allowlist: while `me` loads, nobody is.
 */
export function ChatsScreen() {
  const router = useRouter();
  const toast = useToast();
  const man = useMe().data?.gender === "male";
  const [tier, setTier] = useState<Tier>("threads");
  const [filter, setFilter] = useState<ThreadFilter>("all");
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());

  // Each tab's count is its own unfiltered list, which is also the list shown
  // when nothing narrows it: one request, not two.
  const threads = useThreads("threads", "all", "");
  const knots = useThreads("knots", "all", "");
  const listFilter = tier === "knots" ? filter : "all";
  const narrowed = listFilter !== "all" || q !== "";
  // Asked only while something narrows it; otherwise the tab's own list shows.
  const narrowedList = useThreads(tier, listFilter, q, narrowed);
  const list = narrowed ? narrowedList : tier === "threads" ? threads : knots;

  const clearOne = useClearThread();
  const restore = useRestoreThread();
  const clearMany = useClearThreads();

  useEffect(() => {
    const timer = setTimeout(
      () => setQ(text.trim().slice(0, THREADS_Q_MAX)),
      SEARCH_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [text]);

  const end = useRef<HTMLDivElement>(null);
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = list;
  useEffect(() => {
    const node = end.current;
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

  const rows = list.data?.pages.flatMap((page) => page.items);
  const tierRows = (tier === "threads" ? threads : knots).data?.pages.flatMap(
    (page) => page.items,
  );
  const hasAny = (tierRows?.length ?? 0) > 0;
  const atCap = selected.size >= CLEAR_MAX;

  function changeTier(next: Tier) {
    setTier(next);
    setSelecting(false);
    setSelected(new Set());
  }

  function toggle(id: string) {
    setSelected((was) => {
      const next = new Set(was);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function onClear(row: ThreadRow) {
    clearOne.mutate(row.id, {
      onSuccess: () =>
        // Offered only once the clearing is the server's, so an Undo can't
        // reach it first.
        toast.show({
          message: t("chats.cleared"),
          durationMs: UNDO_MS,
          action: {
            label: t("chats.undo"),
            onClick: () =>
              restore.mutate(row.id, {
                onError: () =>
                  toast.show({
                    message: t("chats.restoreFailed"),
                    tone: "error",
                  }),
              }),
          },
        }),
      onError: () =>
        toast.show({ message: t("chats.clearFailed"), tone: "error" }),
    });
  }

  function onClearMany(what: { thread_ids: string[] } | { expired: true }) {
    clearMany.mutate(what, {
      onSuccess: ({ cleared }) => {
        setSelecting(false);
        setSelected(new Set());
        toast.show({
          message: t(
            cleared === 1 ? "chats.clearedMany.one" : "chats.clearedMany.other",
            { count: cleared },
          ),
        });
      },
      onError: () =>
        toast.show({ message: t("chats.clearFailed"), tone: "error" }),
    });
  }

  let content: ReactNode;
  if (rows === undefined) {
    content = list.isError ? (
      <ErrorState
        title={t("chats.failed")}
        onRetry={() => void list.refetch()}
      />
    ) : (
      <div className="flex flex-col gap-4 p-(--shell-gutter)">
        {[0, 1, 2].map((n) => (
          <div key={n} className="flex items-center gap-3">
            <Skeleton variant="avatar" className="size-12" />
            <div className="flex flex-1 flex-col gap-2">
              <Skeleton className="w-1/3" />
              <Skeleton className="w-2/3" />
            </div>
          </div>
        ))}
      </div>
    );
  } else if (rows.length === 0) {
    content = (
      <div className="rounded-swipe border-line-strong m-(--shell-gutter) border-2 border-dashed">
        {narrowed ? (
          <EmptyState
            icon={Search}
            title={t("chats.noResults")}
            body={t("chats.noResultsBody")}
          />
        ) : (
          <EmptyState
            icon={tier === "threads" ? MessageCircle : Link2}
            title={t(
              tier === "threads" ? "chats.emptyThreads" : "chats.emptyKnots",
            )}
            body={t(
              tier === "threads"
                ? "chats.emptyThreadsBody"
                : "chats.emptyKnotsBody",
            )}
            action={{
              label: t("chats.emptyAction"),
              onClick: () => router.push("/discover"),
              variant: "primary",
            }}
          />
        )}
      </div>
    );
  } else {
    content = (
      <>
        <ul>
          {rows.map((row) => (
            <ChatRow
              key={row.id}
              row={row}
              man={man}
              selecting={selecting}
              selected={selected.has(row.id)}
              selectDisabled={atCap && !selected.has(row.id)}
              onToggle={() => toggle(row.id)}
              onClear={() => onClear(row)}
            />
          ))}
        </ul>
        <div ref={end} />
        {isFetchingNextPage && (
          <div className="text-mute flex justify-center py-4">
            <Spinner label={t("chats.loadingMore")} />
          </div>
        )}
        {isFetchNextPageError && (
          <ErrorState
            title={t("chats.failed")}
            onRetry={() => void fetchNextPage()}
          />
        )}
      </>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">{t("chats.title")}</h1>
      <div className="border-line flex items-end justify-between border-b px-(--shell-gutter)">
        <ChatsTabs
          tier={tier}
          counts={{
            threads: countOf(threads.data?.pages),
            knots: countOf(knots.data?.pages),
          }}
          onChange={changeTier}
        />
        {hasAny && (
          <button
            type="button"
            aria-pressed={selecting}
            onClick={() => {
              setSelecting((was) => !was);
              setSelected(new Set());
            }}
            className="text-small focus-visible:outline-accent pb-2.5 font-semibold focus-visible:outline-2"
          >
            <span className={selecting ? "text-accent" : "text-mute"}>
              {t(selecting ? "chats.done" : "chats.select")}
            </span>
          </button>
        )}
      </div>

      {(hasAny || narrowed) && (
        <div className="flex flex-col gap-3 px-(--shell-gutter) pt-3">
          {tier === "knots" && (
            <div
              role="group"
              aria-label={t("chats.filters")}
              className="flex gap-2"
            >
              {FILTERS.map(([value, key]) => (
                <Chip
                  key={value}
                  active={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {t(key)}
                </Chip>
              ))}
            </div>
          )}
          <label className="rounded-pill border-line bg-surface focus-within:outline-accent flex items-center gap-2 border px-4 py-2 focus-within:outline-2 focus-within:outline-offset-2">
            <Icon icon={Search} size={16} className="text-mute" />
            <input
              type="search"
              value={text}
              maxLength={THREADS_Q_MAX}
              onChange={(event) => setText(event.target.value)}
              placeholder={t("chats.search")}
              aria-label={t("chats.search")}
              className="text-input text-ink placeholder:text-mute min-w-0 flex-1 bg-transparent outline-none"
            />
          </label>
          {man && tier === "threads" && !selecting && threads.data && (
            <ClearExpired
              rows={threads.data.pages.flatMap((page) => page.items)}
              busy={clearMany.isPending}
              onClear={() => onClearMany({ expired: true })}
            />
          )}
          {selecting && selected.size > 0 && (
            <Button
              fullWidth
              loading={clearMany.isPending}
              onClick={() => onClearMany({ thread_ids: [...selected] })}
            >
              {t(
                selected.size === 1
                  ? "chats.clearSelected.one"
                  : "chats.clearSelected.other",
                { count: selected.size },
              )}
            </Button>
          )}
          {selecting && atCap && (
            <p className="text-small text-mute">
              {t("chats.selectLimit", { max: CLEAR_MAX })}
            </p>
          )}
        </div>
      )}

      <section
        aria-label={t(tier === "threads" ? "chats.threads" : "chats.knots")}
        aria-busy={rows === undefined && !list.isError}
        className="flex-1"
      >
        {content}
      </section>

      {man && (
        <p className="text-small text-mute px-(--shell-gutter) py-4 text-center">
          {t("chats.footer")}
        </p>
      )}
    </div>
  );
}

/**
 * "Clear expired (n)", his alone: n is the Threads in his list whose time has
 * run out by the clock, moving with the shared ticker; the server clears every
 * one it counts the same way (`expired: true`, D-560).
 */
function ClearExpired({
  rows,
  busy,
  onClear,
}: {
  rows: ThreadRow[];
  busy: boolean;
  onClear: () => void;
}) {
  const count = ranOut(rows, useNow());
  if (count === 0) return null;
  return (
    <Button variant="ghost" size="sm" loading={busy} onClick={onClear}>
      <Icon icon={Trash2} size={14} />
      {t("chats.clearExpired", { count })}
    </Button>
  );
}
