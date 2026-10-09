"use client";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import {
  type BlockedUser,
  useBlockedUsers,
  useUnblock,
} from "@/lib/queries/safety";

import { nameOf, PersonRow } from "./PersonRow";
import { PagedList, YouSection } from "./YouSection";

/**
 * Whom you block (T-9.8, P-762): the undo the block sheet points to. Unblock
 * lifts it at once (D-860), with no confirmation: it can be blocked again
 * from their profile. Nobody is told either way (D-862). The rows open
 * nothing, since their profile is hidden from you while the block stands.
 */
export function BlockedSection() {
  const blocked = useBlockedUsers();
  return (
    <YouSection title={t("you.blocked.title")}>
      <PagedList
        query={blocked}
        empty={t("you.blocked.empty")}
        failed={t("you.blocked.failed")}
        row={(item) => <Row key={item.user.id} item={item} />}
      />
    </YouSection>
  );
}

function Row({ item }: { item: BlockedUser }) {
  const unblock = useUnblock();
  const toast = useToast();
  const name = nameOf(item.user);
  return (
    <PersonRow
      person={item.user}
      action={
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("you.blocked.unblockName", { name })}
          loading={unblock.isPending}
          onClick={() =>
            unblock.mutate(item.user.id, {
              onSuccess: () =>
                toast.show({ message: t("you.blocked.unblocked", { name }) }),
              onError: () =>
                toast.show({
                  message: t("you.blocked.unblockFailed", { name }),
                  tone: "error",
                }),
            })
          }
        >
          {t("you.blocked.unblock")}
        </Button>
      }
    />
  );
}
