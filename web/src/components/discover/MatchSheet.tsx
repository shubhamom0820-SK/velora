"use client";

import { useRouter } from "next/navigation";

import { PushAsk } from "@/components/notifications/PushAsk";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import { useOpenThread } from "@/lib/queries/discover";

export type Match = {
  matchId: string;
  /** The person swiped, whose like was already there (T-6.4). */
  theirName: string;
};

type MatchSheetProps = {
  match: Match | null;
  myName: string;
  /**
   * What opening the Thread costs, from `/prices`: a number for a man, null
   * for a woman (free, D-098), undefined while it loads (his button waits).
   */
  openPrice: number | null | undefined;
  onClose: () => void;
};

function initialOf(name: string): string {
  return Array.from(name.trim())[0]?.toUpperCase() ?? "";
}

/**
 * The match sheet ✦ (08-DESIGN §8): two initials joined by the thread, its
 * ring at the middle; the one whose like was there first ringed in
 * `--chrome-accent`. "Open thread · 5 Velas" for him, "· Free" for her, the
 * number from `/prices` and sent back as `shown_price` (P-56, D-600). Below
 * them, once per browser, the ask for notifications (T-9.4).
 */
export function MatchSheet({
  match,
  myName,
  openPrice,
  onClose,
}: MatchSheetProps) {
  const open = useOpenThread();
  const toast = useToast();
  const router = useRouter();
  const waiting = openPrice === undefined;

  async function openThread() {
    if (!match || waiting) return;
    try {
      await open.mutateAsync({
        match_id: match.matchId,
        shown_price: openPrice ?? 0,
      });
      onClose();
      router.push("/chats");
    } catch (error) {
      if (!(error instanceof ApiError)) {
        toast.show({ message: t("discover.errors.openFailed"), tone: "error" });
      } else if (error.code === "PRICE_CHANGED") {
        const price = Number(error.details?.price);
        toast.show({
          message: t("discover.errors.priceChanged", {
            velas: creditsText(price),
          }),
          tone: "error",
        });
      } else if (error.code !== "INSUFFICIENT_CREDITS") {
        // Out of Velas opens the store sheet instead (QueryProvider).
        toast.show({ message: t("discover.errors.openFailed"), tone: "error" });
      }
    }
  }

  return (
    <Sheet
      open={match !== null}
      onClose={onClose}
      tone="chrome"
      title={t("discover.match.title", { name: match?.theirName ?? "" })}
      lead={
        <div aria-hidden className="mb-4 flex items-center">
          <span className="rounded-pill bg-chrome-line text-title-1 text-chrome-ink flex size-24 items-center justify-center">
            {initialOf(myName)}
          </span>
          <span className="relative flex w-12 items-center justify-center">
            <span className="bg-accent h-0.5 w-full" />
            <span className="rounded-pill border-accent bg-chrome absolute size-3.5 border-2" />
          </span>
          <span className="rounded-pill bg-chrome-line border-chrome-accent text-title-1 text-chrome-ink flex size-24 items-center justify-center border-2">
            {initialOf(match?.theirName ?? "")}
          </span>
        </div>
      }
    >
      <div className="flex flex-col gap-3 pt-4">
        <Button
          fullWidth
          loading={open.isPending}
          disabled={waiting}
          onClick={() => void openThread()}
        >
          {typeof openPrice === "number"
            ? t("discover.match.open", { velas: creditsText(openPrice) })
            : openPrice === null
              ? t("discover.match.openFree")
              : t("discover.match.openPlain")}
        </Button>
        <Button variant="chrome" fullWidth onClick={onClose}>
          {t("discover.match.keepSwiping")}
        </Button>
        <p className="text-micro text-chrome-mute text-center">
          {t("discover.match.footer")}
        </p>
        {/* After a match, never on load (T-9.4): once per browser. */}
        {match !== null && <PushAsk />}
      </div>
    </Sheet>
  );
}
