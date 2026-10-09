"use client";

import { Ellipsis, Trash2, Unlink, User } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { buttonClasses } from "@/components/ui/buttonClasses";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { t } from "@/i18n/t";

type ConversationMenuProps = {
  /** Their profile, unless they deleted their account. */
  profileId: string | null;
  knotted: boolean;
  clearing: boolean;
  untying: boolean;
  onClear: () => void;
  onUntie: () => Promise<boolean>;
};

/**
 * The conversation's ⋯ menu: their profile (`/people/[id]`), "Clear chat"
 * (T-7.8's one-sided clear: the other person keeps theirs), and on a Knot,
 * "Untie the knot", asked twice. Report and Block join with T-9.1 (P-442).
 */
export function ConversationMenu({
  profileId,
  knotted,
  clearing,
  untying,
  onClear,
  onUntie,
}: ConversationMenuProps) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);

  async function untie() {
    if (await onUntie()) {
      setConfirming(false);
      setOpen(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-chrome-ink focus-visible:outline-accent rounded-pill relative -mr-1 p-1 before:absolute before:-inset-1.5 focus-visible:outline-2"
      >
        <Icon icon={Ellipsis} size={22} label={t("conversation.more")} />
      </button>
      <Sheet
        open={open && !confirming}
        onClose={() => setOpen(false)}
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
              onClick={() => setConfirming(true)}
            >
              <Icon icon={Unlink} size={18} />
              {t("conversation.untie")}
            </Button>
          )}
        </div>
      </Sheet>
      <Sheet
        open={confirming}
        onClose={() => setConfirming(false)}
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
            <Button
              variant="ghost"
              fullWidth
              onClick={() => setConfirming(false)}
            >
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
