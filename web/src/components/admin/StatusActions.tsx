"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmAction } from "./ConfirmAction";
import { t, type MessageKey } from "@/i18n/t";
import {
  useSetStatus,
  type AdminUserDetail,
  type StatusTarget,
} from "@/lib/queries/admin";

type Move = { to: StatusTarget; label: MessageKey; adminOnly: boolean };

/**
 * What staff can do to an account's status from where it stands (D-922): a
 * moderator may freeze; banning, and lifting a ban or a freeze, is an admin's.
 * An erased account is banned and unbanned by its number alone. An underage
 * ban is never lifted (D-991), so it offers no unban. The API decides; these
 * are only the buttons worth showing.
 */
function movesFor(detail: AdminUserDetail): Move[] {
  const { status, erased } = detail.user;
  const permanent = detail.ban?.permanent === true;
  if (erased) {
    return detail.ban?.reason === "ban" && !permanent
      ? [{ to: "active", label: "admin.user.unban", adminOnly: true }]
      : detail.ban
        ? []
        : [{ to: "banned", label: "admin.user.ban", adminOnly: true }];
  }
  const moves: Move[] = [];
  if (status === "active" || status === "paused") {
    moves.push({ to: "frozen", label: "admin.user.freeze", adminOnly: false });
  }
  if (status === "frozen") {
    moves.push({ to: "active", label: "admin.user.unfreeze", adminOnly: true });
  }
  if (status === "banned") {
    if (!permanent) {
      moves.push({ to: "active", label: "admin.user.unban", adminOnly: true });
    }
  } else {
    moves.push({ to: "banned", label: "admin.user.ban", adminOnly: true });
  }
  return moves;
}

export function StatusActions({
  detail,
  isAdmin,
}: {
  detail: AdminUserDetail;
  isAdmin: boolean;
}) {
  const [move, setMove] = useState<Move | null>(null);
  const setStatus = useSetStatus(detail.user.id);
  const moves = movesFor(detail).filter((each) => isAdmin || !each.adminOnly);

  if (moves.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {moves.map((each) => (
        <Button
          key={each.label}
          size="sm"
          variant={each.to === "active" ? "ghost" : "danger"}
          onClick={() => {
            setStatus.reset();
            setMove(each);
          }}
        >
          {t(each.label)}
        </Button>
      ))}
      {move && (
        <ConfirmAction
          open
          onClose={() => setMove(null)}
          title={t(move.label)}
          confirmLabel={t(move.label)}
          variant={move.to === "active" ? "primary" : "danger"}
          pending={setStatus.isPending}
          error={setStatus.error}
          onConfirm={(reason) =>
            setStatus.mutate(
              { status: move.to, reason },
              { onSuccess: () => setMove(null) },
            )
          }
        />
      )}
    </div>
  );
}
