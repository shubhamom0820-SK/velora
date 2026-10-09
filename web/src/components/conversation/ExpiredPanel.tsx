"use client";

import { Button } from "@/components/ui/Button";
import { t } from "@/i18n/t";
import { creditsText } from "@/lib/credits";

type ExpiredPanelProps = {
  /** She wrote after the hour ran out (08-DESIGN §8's case). */
  sheWrote: boolean;
  /** `/prices`' `thread_reopen` and `thread_extend`; undefined while loading. */
  reopenPrice: number | undefined;
  extendPrice: number | undefined;
  busy: "reopen" | "extend" | "tie" | null;
  onReopen: () => void;
  onReopenAndKeep: () => void;
  onTie: () => void;
};

/**
 * His expired Thread's panel (08-DESIGN §8, D-097, D-253), at the bottom in
 * place of the composer: everything above stays readable. "Re-open · 2
 * Velas" filled, "Re-open and keep it for 24h · 10 Velas" outlined (one
 * Extend from expired, never twelve), and, quieter, "Tie the knot", which an
 * expired Thread takes too (T-7.7). Each price is the one `/prices` gave, and
 * the one sent back (P-56). A woman never sees this panel.
 */
export function ExpiredPanel({
  sheWrote,
  reopenPrice,
  extendPrice,
  busy,
  onReopen,
  onReopenAndKeep,
  onTie,
}: ExpiredPanelProps) {
  return (
    <section
      aria-labelledby="expired-title"
      className="bg-surface rounded-t-sheet shadow-2 flex flex-col gap-3 px-(--shell-gutter) pt-5 pb-4"
    >
      <h2 id="expired-title" className="text-title-2 text-ink">
        {t(
          sheWrote
            ? "conversation.expired.titleWrote"
            : "conversation.expired.title",
        )}
      </h2>
      <p className="text-small text-mute">
        {t(
          sheWrote
            ? "conversation.expired.bodyWrote"
            : "conversation.expired.body",
        )}
      </p>
      <Button
        fullWidth
        disabled={
          reopenPrice === undefined || (busy !== null && busy !== "reopen")
        }
        loading={busy === "reopen"}
        onClick={onReopen}
      >
        {t("conversation.expired.reopen", {
          velas: reopenPrice === undefined ? "…" : creditsText(reopenPrice),
        })}
      </Button>
      <Button
        variant="danger"
        fullWidth
        disabled={
          extendPrice === undefined || (busy !== null && busy !== "extend")
        }
        loading={busy === "extend"}
        onClick={onReopenAndKeep}
      >
        {t("conversation.expired.reopenKeep", {
          velas: extendPrice === undefined ? "…" : creditsText(extendPrice),
        })}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={busy !== null && busy !== "tie"}
        loading={busy === "tie"}
        onClick={onTie}
      >
        {t("conversation.tie")}
      </Button>
      <p className="text-micro text-mute text-center">
        {t("conversation.expired.note")}
      </p>
    </section>
  );
}
