import { SlidersHorizontal, Users } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { t } from "@/i18n/t";

type DiscoverEmptyProps =
  | { kind: "nobody"; onCheckAgain: () => void }
  | { kind: "filters"; onClear: () => void };

/**
 * The deck with no one left (08-DESIGN §8): a dashed `--line-strong` outline
 * in the card's shape. Either nobody new is nearby, or the filters left no
 * one, and then the one action clears them.
 */
export function DiscoverEmpty(props: DiscoverEmptyProps) {
  return (
    <div className="rounded-swipe border-line-strong flex h-[min(35rem,calc(100dvh-17rem))] min-h-96 w-full flex-col justify-center border-2 border-dashed">
      {props.kind === "filters" ? (
        <EmptyState
          icon={SlidersHorizontal}
          title={t("discover.empty.filtersTitle")}
          body={t("discover.empty.filtersBody")}
          action={{
            label: t("discover.empty.clear"),
            onClick: props.onClear,
            variant: "primary",
          }}
        />
      ) : (
        <EmptyState
          icon={Users}
          title={t("discover.empty.nobodyTitle")}
          body={t("discover.empty.nobodyBody")}
          action={{
            label: t("discover.empty.checkAgain"),
            onClick: props.onCheckAgain,
            variant: "primary",
          }}
        />
      )}
    </div>
  );
}
