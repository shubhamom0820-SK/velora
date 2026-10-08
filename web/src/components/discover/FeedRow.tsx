import { Search } from "lucide-react";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { Feed } from "@/lib/queries/discover";

export const FEEDS: readonly Feed[] = ["foryou", "new", "online"];

type FeedRowProps = {
  feed: Feed;
  onFeed: (feed: Feed) => void;
};

/**
 * For you, New and Online as pills, the current one filled `--ink`; Search at
 * the row's end, to T-6.6's screen (P-443). Filters joins it with T-6.9's
 * sheet, and Liked you with T-6.7's screen and count.
 */
export function FeedRow({ feed, onFeed }: FeedRowProps) {
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
        className="rounded-pill border-line bg-surface text-ink focus-visible:outline-accent relative flex size-10 shrink-0 items-center justify-center border before:absolute before:-inset-0.5 focus-visible:outline-2"
      >
        <Icon icon={Search} size={18} />
      </Link>
    </div>
  );
}
