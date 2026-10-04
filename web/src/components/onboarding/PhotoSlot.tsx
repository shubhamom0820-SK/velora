"use client";

import { ChevronLeft, ChevronRight, ImageOff, Plus, X } from "lucide-react";
import { useState, type DragEvent } from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { Photo } from "@/lib/queries/photos";

import { PhotoChecking } from "./PhotoChecking";
import type { SlotView } from "./usePhotoSlots";

type PhotoSlotProps = {
  view: SlotView;
  /** Its place, 0 to 5; 0 is the main photo. */
  place: number;
  /** Photos are moving about: nothing may be removed, moved or dragged. */
  busy: boolean;
  /** Places are being rewritten: nothing may be added either. */
  locked: boolean;
  /** Its order among the live photos, for the move buttons. */
  first: boolean;
  last: boolean;
  /** Open the picker for a photo for this slot. */
  onChoose: () => void;
  onRetry: () => void;
  onDismiss: () => void;
  onRemove: (photo: Photo) => void;
  onMove: (by: -1 | 1) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDrop: () => void;
};

const ON_PHOTO =
  "bg-chrome/80 text-on-photo rounded-pill flex items-center justify-center";
// 24 px drawn, 44 px to tap (08-DESIGN §3).
const SMALL_BUTTON =
  "relative size-6 before:absolute before:-inset-2.5 before:content-[''] disabled:opacity-40 focus-visible:outline-accent focus-visible:outline-2";

function liveSource(view: SlotView): string | null {
  return view.kind === "checking" || view.kind === "approved"
    ? (view.preview ?? view.photo.url)
    : null;
}

/**
 * One of the photos step's six slots (T-4.6), in whichever state the plan
 * names: empty, uploading (a percentage), checking, approved, or rejected with
 * its reason and a way on. Laid out as the prototype's: 3:4, "Main" on the
 * first, the remove cross top right. Up and down are the buttons beside a
 * photo, always shown on touch screens, where dragging isn't to be had.
 */
export function PhotoSlot({
  view,
  place,
  busy,
  locked,
  first,
  last,
  onChoose,
  onRetry,
  onDismiss,
  onRemove,
  onMove,
  onDragStart,
  onDragEnd,
  onDrop,
}: PhotoSlotProps) {
  const n = place + 1;
  // A live photo keeps the link it was first shown by: each fresh list signs a
  // new one, and a new src would fetch the photo again. A link that has
  // expired by the time it loads falls back to the newest.
  const [src, setSrc] = useState(() => liveSource(view));
  const live = view.kind === "checking" || view.kind === "approved";

  const drag = live && !busy;
  return (
    <li
      aria-label={t("onboarding.photos.slot", { n })}
      draggable={drag}
      onDragStart={(event: DragEvent) => {
        if (!live) return;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", view.photo.id);
        onDragStart();
      }}
      onDragEnd={onDragEnd}
      onDragOver={(event: DragEvent) => {
        if (live) event.preventDefault();
      }}
      onDrop={(event: DragEvent) => {
        if (!live) return;
        event.preventDefault();
        onDrop();
      }}
      className={cx(
        "group rounded-input bg-surface relative aspect-[3/4] overflow-hidden",
        drag && "cursor-grab",
      )}
    >
      {view.kind === "empty" && (
        <button
          type="button"
          onClick={onChoose}
          disabled={locked}
          className="rounded-input border-line text-mute focus-visible:outline-accent flex size-full items-center justify-center border border-dashed focus-visible:outline-2 disabled:opacity-40"
        >
          <Icon icon={Plus} size={18} label={t("onboarding.photos.add")} />
        </button>
      )}

      {view.kind === "uploading" && (
        <>
          {view.preview && (
            // A plain <img>: next/image would send users' photos through the
            // host's image optimiser, outside India (D-048).
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={view.preview}
              alt=""
              className="size-full object-cover opacity-60"
            />
          )}
          <div className="bg-scrim absolute inset-0 flex flex-col items-center justify-center gap-2 p-2">
            {view.percent < 100 ? (
              <>
                <span className="text-micro text-on-photo">
                  {t("onboarding.photos.uploading", { percent: view.percent })}
                </span>
                <progress
                  max={100}
                  value={view.percent}
                  aria-label={t("onboarding.photos.uploading", {
                    percent: view.percent,
                  })}
                  className="rounded-pill [&::-webkit-progress-bar]:bg-surface-2 [&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent bg-surface-2 h-1 w-3/4 appearance-none overflow-hidden"
                />
              </>
            ) : (
              <PhotoChecking />
            )}
          </div>
        </>
      )}

      {live && src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={t("onboarding.photos.slot", { n })}
          draggable={false}
          onError={() => {
            if (view.photo.url && src !== view.photo.url) {
              setSrc(view.photo.url);
            }
          }}
          className={cx(
            "size-full object-cover",
            view.kind === "checking" && "blur-sm",
          )}
        />
      )}
      {view.kind === "checking" && (
        <div className="bg-scrim absolute inset-0 flex flex-col items-center justify-center">
          <PhotoChecking />
        </div>
      )}
      {view.kind === "approved" && (
        <span className="sr-only">{t("onboarding.photos.approved")}</span>
      )}
      {live && (
        <>
          {place === 0 && (
            <span className="text-micro bg-chrome/80 text-on-photo absolute bottom-1.5 left-1.5 rounded-sm px-1.5 py-0.5">
              {t("onboarding.photos.main")}
            </span>
          )}
          <button
            type="button"
            aria-label={t("onboarding.photos.remove", { n })}
            disabled={busy}
            onClick={() => onRemove(view.photo)}
            className={cx(ON_PHOTO, SMALL_BUTTON, "absolute top-1.5 right-1.5")}
          >
            <Icon icon={X} size={12} />
          </button>
          <div className="pointer-fine:opacity-0 pointer-fine:group-focus-within:opacity-100 pointer-fine:group-hover:opacity-100 absolute right-1.5 bottom-1.5 flex gap-3">
            <button
              type="button"
              aria-label={t("onboarding.photos.moveEarlier", { n })}
              disabled={busy || first}
              onClick={() => onMove(-1)}
              className={cx(ON_PHOTO, SMALL_BUTTON)}
            >
              <Icon icon={ChevronLeft} size={14} />
            </button>
            <button
              type="button"
              aria-label={t("onboarding.photos.moveLater", { n })}
              disabled={busy || last}
              onClick={() => onMove(1)}
              className={cx(ON_PHOTO, SMALL_BUTTON)}
            >
              <Icon icon={ChevronRight} size={14} />
            </button>
          </div>
        </>
      )}

      {(view.kind === "rejected" || view.kind === "failed") && (
        <>
          {view.kind === "failed" && view.preview && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={view.preview}
              alt=""
              className="absolute inset-0 size-full object-cover opacity-20"
            />
          )}
          <div className="border-line bg-surface-2 relative flex size-full flex-col items-center justify-center gap-2 rounded-input border p-2 text-center">
            <Icon icon={ImageOff} size={18} className="text-accent" />
            <p role="alert" className="text-micro text-ink">
              {view.copy}
            </p>
            <button
              type="button"
              disabled={locked}
              onClick={view.kind === "rejected" ? onChoose : onRetry}
              className="text-micro text-accent focus-visible:outline-accent underline underline-offset-2 focus-visible:outline-2 disabled:opacity-40"
            >
              {view.kind === "rejected"
                ? t("onboarding.photos.chooseAnother")
                : t("onboarding.photos.tryAgain")}
            </button>
          </div>
          <button
            type="button"
            aria-label={t("onboarding.photos.dismiss", { n })}
            disabled={busy}
            onClick={onDismiss}
            className={cx(ON_PHOTO, SMALL_BUTTON, "absolute top-1.5 right-1.5")}
          >
            <Icon icon={X} size={12} />
          </button>
        </>
      )}
    </li>
  );
}
