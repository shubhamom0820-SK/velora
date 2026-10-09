"use client";

import { Ban, Ellipsis, Flag, Trash2, Unlink, User } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BlockSheet } from "@/components/profile/BlockSheet";
import { ReportSheet } from "@/components/profile/ReportSheet";
import { Button } from "@/components/ui/Button";
import { buttonClasses } from "@/components/ui/buttonClasses";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { t } from "@/i18n/t";

type ConversationMenuProps = {
  threadId: string;
  /** Who they are: reported or blocked by this id, even once deleted. */
  otherId: string;
  /** Their name, or "Deleted account". */
  theirName: string;
  /** Their profile, unless they deleted their account. */
  profileId: string | null;
  knotted: boolean;
  clearing: boolean;
  untying: boolean;
  onClear: () => void;
  onUntie: () => Promise<boolean>;
  /** They are blocked (by the sheet, or a report's "Also block"). */
  onBlocked: () => void;
};

type Open = "menu" | "confirm" | "report" | "block" | null;

/**
 * The conversation's ⋯ menu: their profile (`/people/[id]`), "Clear chat"
 * (T-7.8's one-sided clear: the other person keeps theirs), on a Knot "Untie
 * the knot", asked twice, and T-9.1's Report and Block (P-764): the same
 * sheets as the profile's, the report naming this Thread, here even when
 * their account is deleted and no profile is left to open. A block is
 * silent (D-862), and the chat is gone for both, so the screen leaves it.
 */
export function ConversationMenu({
  threadId,
  otherId,
  theirName,
  profileId,
  knotted,
  clearing,
  untying,
  onClear,
  onUntie,
  onBlocked,
}: ConversationMenuProps) {
  const [open, setOpen] = useState<Open>(null);

  async function untie() {
    if (await onUntie()) setOpen(null);
  }

  function blocked() {
    setOpen(null);
    onBlocked();
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen("menu")}
        className="text-chrome-ink focus-visible:outline-accent rounded-pill relative -mr-1 p-1 before:absolute before:-inset-1.5 focus-visible:outline-2"
      >
        <Icon icon={Ellipsis} size={22} label={t("conversation.more")} />
      </button>
      <Sheet
        open={open === "menu"}
        onClose={() => setOpen(null)}
        title={t("conversation.more")}
      >
        <div className="flex flex-col gap-2">
          {profileId !== null && (
            <Link
              href={`/people/${profileId}`}
              className={buttonClasses({ variant: "ghost", fullWidth: true })}
            >
              <Icon icon={User} size={18} />
              {t("conversation.viewProfile")}
            </Link>
          )}
          <Button
            variant="ghost"
            fullWidth
            loading={clearing}
            onClick={onClear}
          >
            <Icon icon={Trash2} size={18} />
            {t("conversation.clearChat")}
          </Button>
          {knotted && (
            <Button
              variant="danger"
              fullWidth
              onClick={() => setOpen("confirm")}
            >
              <Icon icon={Unlink} size={18} />
              {t("conversation.untie")}
            </Button>
          )}
          <Button
            variant="ghost"
            fullWidth
            onClick={() => setOpen("report")}
            className="text-accent"
          >
            <Icon icon={Flag} size={18} />
            {t("profile.report")}
          </Button>
          <Button
            variant="ghost"
            fullWidth
            onClick={() => setOpen("block")}
            className="text-accent"
          >
            <Icon icon={Ban} size={18} />
            {t("profile.block", { name: theirName })}
          </Button>
        </div>
      </Sheet>
      <ReportSheet
        open={open === "report"}
        userId={otherId}
        firstName={theirName}
        threadId={threadId}
        onClose={(gone) => (gone ? blocked() : setOpen(null))}
      />
      <BlockSheet
        open={open === "block"}
        userId={otherId}
        firstName={theirName}
        onClose={() => setOpen(null)}
        onBlocked={blocked}
      />
      <Sheet
        open={open === "confirm"}
        onClose={() => setOpen(null)}
        title={t("conversation.untieTitle")}
        footer={
          <div className="flex flex-col gap-2">
            <Button
              variant="danger"
              fullWidth
              loading={untying}
              onClick={() => void untie()}
            >
              {t("conversation.untieConfirm")}
            </Button>
            <Button variant="ghost" fullWidth onClick={() => setOpen(null)}>
              {t("conversation.untieKeep")}
            </Button>
          </div>
        }
      >
        <p className="text-body text-mute">{t("conversation.untieBody")}</p>
      </Sheet>
    </>
  );
}
