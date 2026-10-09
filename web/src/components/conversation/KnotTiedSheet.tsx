"use client";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { t } from "@/i18n/t";

type KnotTiedSheetProps = {
  open: boolean;
  myName: string;
  theirName: string;
  /** His words name the hour and Velas; hers never do (D-097, P-460). */
  man: boolean;
  onClose: () => void;
};

function initialOf(name: string): string {
  return Array.from(name.trim())[0]?.toUpperCase() ?? "";
}

/**
 * Knot tied ✦ (08-DESIGN §8, P-670): the match sheet again, but both initials
 * ringed in `--chrome-accent` and the ring between them filled. Shown when my
 * tap was the second and made the Knot. "Keep talking" closes it. His footer
 * is the match sheet's; hers has none: it would name the hour.
 */
export function KnotTiedSheet({
  open,
  myName,
  theirName,
  man,
  onClose,
}: KnotTiedSheetProps) {
  const initial =
    "rounded-pill bg-chrome-line border-chrome-accent text-title-1 text-chrome-ink flex size-24 items-center justify-center border-2";
  return (
    <Sheet
      open={open}
      onClose={onClose}
      tone="chrome"
      title={t("conversation.tied.title", { name: theirName })}
      lead={
        <div aria-hidden className="mb-4 flex items-center">
          <span className={initial}>{initialOf(myName)}</span>
          <span className="relative flex w-12 items-center justify-center">
            <span className="bg-chrome-accent h-0.5 w-full" />
            <span className="rounded-pill bg-chrome-accent shadow-1 absolute flex size-7 items-center justify-center">
              <span className="rounded-pill border-chrome size-3.5 border-2" />
            </span>
          </span>
          <span className={initial}>{initialOf(theirName)}</span>
        </div>
      }
    >
      <div className="flex flex-col gap-3 pt-2">
        <p className="text-body text-chrome-mute text-center">
          {t(man ? "conversation.tied.bodyHis" : "conversation.tied.bodyHers")}
        </p>
        <Button fullWidth onClick={onClose}>
          {t("conversation.tied.keepTalking")}
        </Button>
        {man && (
          <p className="text-micro text-chrome-mute text-center">
            {t("discover.match.footer")}
          </p>
        )}
      </div>
    </Sheet>
  );
}
