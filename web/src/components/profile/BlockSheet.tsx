"use client";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/useToast";
import { t, type MessageKey } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { useBlock } from "@/lib/queries/safety";

const WHAT_HAPPENS = [
  "profile.blockTheyWont",
  "profile.blockYouWont",
  "profile.blockThreads",
  "profile.blockSilent",
  // P-762: the You tab's blocked list (T-9.8).
  "profile.blockUndo",
] as const satisfies readonly MessageKey[];

type BlockSheetProps = {
  open: boolean;
  userId: string;
  firstName: string;
  onClose: () => void;
  /** The block is made: the screen should go. */
  onBlocked: () => void;
};

/**
 * Block someone (T-9.1, 08-DESIGN §5's block sheet): what a block does, in
 * the prototype's five lines, then the confirm. Undoing it is the You tab's
 * blocked list (T-9.8, P-762).
 */
export function BlockSheet({
  open,
  userId,
  firstName,
  onClose,
  onBlocked,
}: BlockSheetProps) {
  const block = useBlock();
  const toast = useToast();

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={t("profile.blockTitle", { name: firstName })}
      footer={
        <div className="flex flex-col gap-2">
          <Button
            variant="danger"
            fullWidth
            loading={block.isPending}
            onClick={() =>
              block.mutate(userId, {
                onSuccess: onBlocked,
                onError: () =>
                  toast.show({
                    message: t("profile.blockFailed", { name: firstName }),
                    tone: "error",
                  }),
              })
            }
          >
            {t("profile.block", { name: firstName })}
          </Button>
          <Button variant="ghost" fullWidth onClick={onClose}>
            {t("profile.blockCancel")}
          </Button>
        </div>
      }
    >
      <ul className="bg-bg rounded-card border-line flex flex-col gap-2 border p-4">
        {WHAT_HAPPENS.map((key) => (
          <li key={key} className="text-small text-ink flex gap-2">
            <span aria-hidden className="text-accent">
              ·
            </span>
            {t(key, { app: APP_NAME })}
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
