"use client";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import {
  type ThreadRow,
  useClearedThreads,
  useRestoreThread,
} from "@/lib/queries/threads";

import { nameOf, PersonRow } from "./PersonRow";
import { PagedList, YouSection } from "./YouSection";

/**
 * The chats you cleared (T-9.8, P-510, D-912): each restored on its own, the
 * whole history back (D-611), never all at once. No preview of what was
 * cleared, only whose chat it is; restored, it is back in Chats.
 */
export function ClearedSection() {
  const cleared = useClearedThreads();
  return (
    <YouSection title={t("you.cleared.title")} body={t("you.cleared.body")}>
      <PagedList
        query={cleared}
        empty={t("you.cleared.empty")}
        failed={t("you.cleared.failed")}
        row={(row) => <Row key={row.id} row={row} />}
      />
    </YouSection>
  );
}

function Row({ row }: { row: ThreadRow }) {
  const restore = useRestoreThread();
  const toast = useToast();
  const name = nameOf(row.other);
  return (
    <PersonRow
      person={row.other}
      action={
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("you.cleared.restoreName", { name })}
          loading={restore.isPending}
          onClick={() =>
            restore.mutate(row.id, {
              onSuccess: () =>
                toast.show({ message: t("you.cleared.restored") }),
              onError: () =>
                toast.show({
                  message: t("you.cleared.restoreFailed"),
                  tone: "error",
                }),
            })
          }
        >
          {t("you.cleared.restore")}
        </Button>
      }
    />
  );
}
