import { Heart, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { Feed } from "@/lib/queries/discover";
import { useLikesCount } from "@/lib/queries/likes";

export const FEEDS: readonly Feed[] = ["foryou", "new", "online"];

type FeedRowProps = {
  feed: Feed;
  onFeed: (feed: Feed) => void;
  /** How many filters are on: the Filters button's badge (T-6.9). */
  filterCount: number;
  onFilters: () => void;
};

const ICON_BUTTON =
  "rounded-pill border-line bg-surface text-ink focus-visible:outline-accent relative flex size-10 shrink-0 items-center justify-center border before:absolute before:-inset-0.5 focus-visible:outline-2";

/**
 * For you, New and Online as pills, the current one filled `--ink`; Search at
 * the row's end, to T-6.6's screen, and Liked you, to T-6.7's, with how many
 * are waiting (P-443); then Filters, T-6.9's sheet, with the count of filters
 * on as an `--accent` badge.
 */
export function FeedRow({
  feed,
  onFeed,
  filterCount,
  onFilters,
}: FeedRowProps) {
  const waiting = useLikesCount().data?.count ?? 0;
  return (
    <div className="flex items-center gap-2">
      <div
        role="group"
        aria-label={t("discover.feeds.label")}
        className="flex flex-1 gap-2 overflow-x-auto"
      >
        {FEEDS.map((one) => (
          <button
            key={one}
            type="button"
            aria-pressed={one === feed}
            onClick={() => onFeed(one)}
            className={cx(
              "rounded-pill text-ui focus-visible:outline-accent relative shrink-0 px-4 py-2 font-semibold before:absolute before:inset-x-0 before:-inset-y-1 focus-visible:outline-2",
              one === feed
                ? "bg-ink text-chrome-ink"
                : "border-line text-mute border",
            )}
          >
            {t(`discover.feeds.${one}`)}
          </button>
        ))}
      </div>
      <Link
        href="/discover/search"
        aria-label={t("discover.search")}
        className={ICON_BUTTON}
      >
        <Icon icon={Search} size={18} />
      </Link>
      <Link
        href="/discover/likes"
        aria-label={
          waiting > 0
            ? t("likes.entryCount", { count: waiting })
            : t("likes.entry")
        }
        className="rounded-pill border-line bg-surface text-ink focus-visible:outline-accent relative flex size-10 shrink-0 items-center justify-center border before:absolute before:-inset-0.5 focus-visible:outline-2"
      >
        <Icon icon={Heart} size={18} />
        {waiting > 0 && (
          <span aria-hidden className="absolute -top-1.5 -right-1.5">
            <Badge tone="count">{waiting}</Badge>
          </span>
        )}
      </Link>
      <button
        type="button"
        aria-label={
          filterCount === 0
            ? t("discover.filters.open")
            : t(
                filterCount === 1
                  ? "discover.filters.openCount.one"
                  : "discover.filters.openCount.other",
                { count: filterCount },
              )
        }
        onClick={onFilters}
        className={ICON_BUTTON}
      >
        <Icon icon={SlidersHorizontal} size={18} />
        {filterCount > 0 && (
          <span
            aria-hidden
            data-testid="filter-count"
            className="rounded-pill bg-accent text-on-accent text-micro absolute -top-1 -right-1 flex min-w-5 items-center justify-center px-1.5 py-0.5"
          >
            {filterCount}
          </span>
        )}
      </button>
    </div>
  );
}
