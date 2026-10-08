"use client";

import Link from "next/link";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { t } from "@/i18n/t";
import type { AlbumRequest } from "@/lib/queries/album";

type AlbumRequestRowProps = {
  request: AlbumRequest;
  /** Which of this row's buttons is waiting on the API, if any. */
  busy: "grant" | "decline" | "revoke" | null;
  onDecide: (grant: boolean) => void;
  onRevoke: () => void;
};

/**
 * One request to see your album: who asked (a `CardLite`; a deleted account is
 * named as one, with no link), and Let them see / Decline while it waits, or
 * Stop sharing once granted. Never what they paid (D-732).
 */
export function AlbumRequestRow({
  request,
  busy,
  onDecide,
  onRevoke,
}: AlbumRequestRowProps) {
  const who = request.requester;
  const name = who.deleted
    ? t("albumRequests.deleted")
    : (who.first_name ?? t("albumRequests.deleted"));
  const pending = request.status === "pending";
  return (
    <div className="border-line flex flex-col gap-3 border-b py-4">
      <div className="flex items-center gap-3">
        <Avatar name={name} src={who.main_photo_url ?? undefined} size={44} />
        <div className="flex min-w-0 flex-1 flex-col">
          {who.deleted ? (
            <span className="text-ui text-mute">{name}</span>
          ) : (
            <Link
              href={`/people/${who.id}`}
              className="text-ui text-ink truncate font-semibold"
            >
              {name}
            </Link>
          )}
          <span className="text-small text-mute">
            {pending ? t("albumRequests.wants") : t("albumRequests.sees")}
          </span>
        </div>
      </div>
      <div className="flex gap-2">
        {pending ? (
          <>
            <Button
              size="sm"
              className="flex-1"
              loading={busy === "grant"}
              disabled={busy !== null}
              onClick={() => onDecide(true)}
            >
              {t("albumRequests.grant")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="flex-1"
              loading={busy === "decline"}
              disabled={busy !== null}
              onClick={() => onDecide(false)}
            >
              {t("albumRequests.decline")}
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            loading={busy === "revoke"}
            disabled={busy !== null}
            onClick={onRevoke}
          >
            {t("albumRequests.revoke")}
          </Button>
        )}
      </div>
    </div>
  );
}
