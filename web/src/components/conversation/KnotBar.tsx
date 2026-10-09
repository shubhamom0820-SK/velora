"use client";

import { Link2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";

type KnotBarProps = {
  /** His words or hers (08-DESIGN §8): his name the price, hers never. */
  man: boolean;
  /** I tapped it already: the bar waits for them. */
  iTied: boolean;
  theirName: string;
  busy: boolean;
  onTie: () => void;
};

/**
 * The knot bar (08-DESIGN §8), `--surface`, above the composer until the
 * Thread is a Knot: a half-red thread glyph, a line in each person's words,
 * and "Tie the knot" as an `--accent` outline button; once I've tapped it,
 * the bar waits for the other person. Free for both (D-003).
 */
export function KnotBar({ man, iTied, theirName, busy, onTie }: KnotBarProps) {
  return (
    <div className="bg-surface border-line flex items-center gap-3 border-t px-(--shell-gutter) py-3">
      <span
        aria-hidden
        className="from-accent to-line-strong flex size-8 shrink-0 items-center justify-center rounded-pill bg-linear-to-r text-on-accent"
      >
        <Icon icon={Link2} size={16} />
      </span>
      {iTied ? (
        <p className="text-small text-mute flex-1">
          {t("conversation.waiting", { name: theirName })}
        </p>
      ) : (
        <>
          <p className="text-small text-ink flex-1">
            {t(man ? "conversation.knotBarHis" : "conversation.knotBarHers")}
          </p>
          <Button variant="danger" size="sm" loading={busy} onClick={onTie}>
            {t("conversation.tie")}
          </Button>
        </>
      )}
    </div>
  );
}
