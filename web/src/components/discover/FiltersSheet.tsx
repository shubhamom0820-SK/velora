"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/ErrorState";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { Toggle } from "@/components/ui/Toggle";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import type { DiscoverFilters } from "@/lib/queries/discover";
import { useIntents } from "@/lib/queries/onboarding";

import { activeCount, NO_FILTERS } from "./filterParams";

type FiltersSheetProps = {
  /** The filters in the URL now: the draft starts from them. */
  applied: DiscoverFilters;
  onClose: () => void;
  /** "Show people": the draft, to be written to the URL. */
  onApply: (filters: DiscoverFilters) => void;
};

/** An intent's words from `en.ts` by id (P-26), the database's label only for an id not there. */
function intentLabel(id: number, fallback: string): string {
  const labels: Readonly<Record<string, string>> = en.intents;
  return labels[String(id)] ?? fallback;
}

/**
 * Filters (T-6.9, 08-DESIGN §8): intent chips, "Selfie matched" and "Online
 * now", free for everyone (D-660). A draft until "Show people": each change
 * of filters is a new scroll the server ranks afresh (D-491), so nothing is
 * asked for while the sheet is open, and ✕, Esc or the backdrop leave the
 * deck as it was. "Clear" empties the draft. Mounted only while open, so it
 * starts from the URL every time.
 *
 * "Selfie matched" is D-393's badge, never `is_verified` alone, and its words
 * are D-262's: nothing here says "verified" (`claims.test.ts`).
 */
export function FiltersSheet({ applied, onClose, onApply }: FiltersSheetProps) {
  const intents = useIntents();
  const [draft, setDraft] = useState<DiscoverFilters>(applied);
  const count = activeCount(draft);

  function toggleIntent(id: number) {
    setDraft((now) => ({
      ...now,
      intentIds: now.intentIds.includes(id)
        ? now.intentIds.filter((one) => one !== id)
        : [...now.intentIds, id],
    }));
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={t("discover.filters.title")}
      badge={
        count > 0 && (
          <Badge tone="soft">
            {t(
              count === 1
                ? "discover.filters.count.one"
                : "discover.filters.count.other",
              { count },
            )}
          </Badge>
        )
      }
      footer={
        <div className="flex gap-3">
          <Button
            variant="ghost"
            fullWidth
            onClick={() => setDraft(NO_FILTERS)}
          >
            {t("discover.filters.clear")}
          </Button>
          <Button fullWidth onClick={() => onApply(draft)}>
            {t("discover.filters.show")}
          </Button>
        </div>
      }
    >
      <h3 className="text-small text-mute mb-2.5">
        {t("discover.filters.lookingFor")}
      </h3>
      {intents.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : intents.isError ? (
        <ErrorState
          title={t("discover.filters.intentsFailed")}
          onRetry={() => void intents.refetch()}
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          {intents.data.map((intent) => (
            <Chip
              key={intent.id}
              active={draft.intentIds.includes(intent.id)}
              onClick={() => toggleIntent(intent.id)}
            >
              {intentLabel(intent.id, intent.label)}
            </Chip>
          ))}
        </div>
      )}
      <div className="border-line mt-6 border-t pt-3">
        <Toggle
          label={t("discover.filters.selfie")}
          description={t("discover.filters.selfieBody")}
          checked={draft.verified}
          onChange={(verified) => setDraft((now) => ({ ...now, verified }))}
        />
        <Toggle
          label={t("discover.filters.online")}
          description={t("discover.filters.onlineBody")}
          checked={draft.online}
          onChange={(online) => setDraft((now) => ({ ...now, online }))}
        />
      </div>
    </Sheet>
  );
}
