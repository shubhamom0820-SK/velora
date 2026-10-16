"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { t } from "@/i18n/t";
import {
  useDecidePhoto,
  type AdminPhoto,
  type StaffRejectReason,
} from "@/lib/queries/admin";

import { ConfirmAction } from "./ConfirmAction";
import { refusalText } from "./refusal";

const REASONS: readonly StaffRejectReason[] = [
  "nudity",
  "text_overlay",
  "other",
];

/**
 * A public or private photo, never a selfie or the face photo (D-925): staff
 * approve a pending one, or take down a pending or approved one, saying which
 * of moderation's reasons and why. The model's minor score shows when it was
 * kept (D-101).
 */
export function PhotoCard({ photo }: { photo: AdminPhoto }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<StaffRejectReason | null>(null);
  const decide = useDecidePhoto();
  const kind = photo.kind === "private" ? "private" : "public";

  return (
    <figure className="border-line bg-surface rounded-card flex flex-col gap-2 border p-3">
      {photo.url ? (
        // A plain <img>, as Avatar's: the photo hosts are the CSP's (T-4.6).
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photo.url}
          alt=""
          className="rounded-card aspect-[3/4] w-full object-cover"
        />
      ) : (
        <div className="bg-line rounded-card aspect-[3/4] w-full" />
      )}
      <figcaption className="flex flex-wrap items-center gap-2">
        <Badge tone="soft">{t(`admin.photos.kinds.${kind}`)}</Badge>
        <Badge tone={photo.status === "approved" ? "soft" : "ink"}>
          {photo.status}
        </Badge>
        {photo.reject_reason && <Badge tone="ink">{photo.reject_reason}</Badge>}
        {photo.minor_score !== null && (
          <span className="text-small text-mute">
            {t("admin.photos.minorScore", {
              score: photo.minor_score.toFixed(2),
            })}
          </span>
        )}
      </figcaption>
      {photo.status !== "rejected" && (
        <div className="flex gap-2">
          {photo.status === "pending" && (
            <Button
              size="sm"
              loading={decide.isPending && decide.variables?.approve === true}
              onClick={() => decide.mutate({ id: photo.id, approve: true })}
            >
              {t("admin.photos.approve")}
            </Button>
          )}
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              decide.reset();
              setOpen(true);
            }}
          >
            {t("admin.photos.reject")}
          </Button>
        </div>
      )}
      {!open && decide.isError && (
        <p role="alert" className="text-small text-accent">
          {refusalText(decide.error)}
        </p>
      )}
      <ConfirmAction
        open={open}
        onClose={() => setOpen(false)}
        title={t("admin.photos.rejectTitle")}
        confirmLabel={t("admin.photos.reject")}
        pending={decide.isPending}
        error={decide.error}
        ready={reason !== null}
        onConfirm={(note) => {
          if (reason === null) return;
          decide.mutate(
            { id: photo.id, approve: false, reason, note },
            { onSuccess: () => setOpen(false) },
          );
        }}
      >
        <div role="group" className="flex flex-wrap gap-2">
          {REASONS.map((choice) => (
            <Chip
              key={choice}
              active={reason === choice}
              onClick={() => setReason(choice)}
            >
              {t(`admin.photos.reasons.${choice}`)}
            </Chip>
          ))}
        </div>
      </ConfirmAction>
    </figure>
  );
}
