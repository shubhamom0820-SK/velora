import { Badge } from "@/components/ui/Badge";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { Tier } from "@/lib/queries/threads";

/** A tab's count: the rows of one page, "50+" when there are more (T-7.10). */
export type TabCount = { count: number; more: boolean } | undefined;

type ChatsTabsProps = {
  tier: Tier;
  counts: Record<Tier, TabCount>;
  onChange: (tier: Tier) => void;
};

const TIERS: Tier[] = ["threads", "knots"];

/**
 * Threads and Knots (08-DESIGN §8): underlined, the active one `--accent`,
 * each with its count. Knots are their own tab: a Knot never sits among the
 * Threads.
 */
export function ChatsTabs({ tier, counts, onChange }: ChatsTabsProps) {
  return (
    <div role="group" aria-label={t("chats.title")} className="flex gap-5">
      {TIERS.map((each) => {
        const label = t(each === "threads" ? "chats.threads" : "chats.knots");
        const count = counts[each];
        const active = each === tier;
        return (
          <button
            key={each}
            type="button"
            aria-pressed={active}
            aria-label={
              count &&
              t(count.more ? "chats.tabCountOver" : "chats.tabCount", {
                tab: label,
                count: count.count,
              })
            }
            onClick={() => onChange(each)}
            className={cx(
              "text-ui focus-visible:outline-accent flex items-center gap-1.5 border-b-2 pt-3 pb-2.5 focus-visible:outline-2",
              active
                ? "border-accent text-accent font-semibold"
                : "text-mute border-transparent",
            )}
          >
            {label}
            {count !== undefined && (
              <Badge tone="soft">
                {count.more ? `${count.count}+` : count.count}
              </Badge>
            )}
          </button>
        );
      })}
    </div>
  );
}
