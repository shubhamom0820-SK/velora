"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import {
  type ThreadRow,
  useThreads,
  useUntieKnot,
} from "@/lib/queries/threads";

import { nameOf, PersonRow } from "./PersonRow";
import { PagedList, YouSection } from "./YouSection";

/**
 * Your Knots (T-9.8): each opens its chat, and Untie (D-770) asks first, since
 * it ends what both of you chose. Either of the two may untie.
 */
export function KnotsSection() {
  const knots = useThreads("knots", "all", "");
  const [untying, setUntying] = useState<ThreadRow | null>(null);

  return (
    <YouSection title={t("you.knots.title")}>
      <PagedList
        query={knots}
        empty={t("you.knots.empty")}
        failed={t("you.knots.failed")}
        row={(row) => (
          <PersonRow
            key={row.id}
            person={row.other}
            href={`/chats/${row.id}`}
            action={
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("you.knots.untieName", {
                  name: nameOf(row.other),
                })}
                onClick={() => setUntying(row)}
              >
                {t("you.knots.untie")}
              </Button>
            }
          />
        )}
      />
      {untying && <UntieSheet row={untying} onClose={() => setUntying(null)} />}
    </YouSection>
  );
}

function UntieSheet({ row, onClose }: { row: ThreadRow; onClose: () => void }) {
  const untie = useUntieKnot();
  const toast = useToast();
  const name = nameOf(row.other);
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("you.knots.untieTitle", { name })}
      footer={
        <div className="flex flex-col gap-2">
          <Button
            variant="danger"
            fullWidth
            loading={untie.isPending}
            onClick={() =>
              untie.mutate(row.id, {
                onSuccess: () => {
                  toast.show({ message: t("you.knots.untied") });
                  onClose();
                },
                onError: () =>
                  toast.show({
                    message: t("you.knots.untieFailed"),
                    tone: "error",
                  }),
              })
            }
          >
            {t("you.knots.untieConfirm")}
          </Button>
          <Button variant="ghost" fullWidth onClick={onClose}>
            {t("you.knots.untieCancel")}
          </Button>
        </div>
      }
    >
      <p className="text-body text-mute">{t("you.knots.untieBody")}</p>
    </Sheet>
  );
}
