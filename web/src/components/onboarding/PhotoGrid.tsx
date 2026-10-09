"use client";

import { useRef, useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";

import { PhotoSlot } from "./PhotoSlot";
import {
  PHOTO_SLOTS,
  type SlotView,
  type usePhotoSlots,
} from "./usePhotoSlots";

/**
 * A slot's identity: a live photo's own, so a new photo, or its approval,
 * starts afresh with that photo's link; otherwise its place, so an upload
 * turning into its outcome stays the same element, and keeps focus.
 */
function slotKey(view: SlotView, place: number): string {
  return view.kind === "checking" || view.kind === "approved"
    ? `${place}:${view.photo.id}:${view.kind}`
    : `${place}`;
}

/**
 * The six public places (T-4.6): tapping an empty one opens the picker, never
 * forcing the camera, and the photo goes in the first free place, so the
 * places run 0 onwards. Moved out of the photos step for the You tab's photos
 * screen (T-9.8), which shares it as it is.
 */
export function PhotoGrid({
  grid,
}: {
  grid: ReturnType<typeof usePhotoSlots>;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const target = useRef<number | null>(null);
  const [dragged, setDragged] = useState<string | null>(null);
  const firstFree = grid.slots.findIndex((slot) => slot.kind === "empty");
  // A delete or reorder is rewriting places: an upload can't pick one now.
  const locked = grid.busy && !grid.uploading;

  function choose(place: number) {
    target.current = place;
    picker.current?.click();
  }

  return (
    <>
      <input
        ref={picker}
        type="file"
        accept="image/*"
        tabIndex={-1}
        aria-hidden
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          const place = target.current;
          // Cleared, so choosing the same file again still counts as a change.
          event.target.value = "";
          if (file && place !== null) void grid.add(place, file);
        }}
      />
      {grid.photos.data ? (
        <ol
          aria-label={t("onboarding.photos.grid")}
          className="grid grid-cols-3 gap-2.5"
        >
          {grid.slots.map((view, place) => {
            const photo =
              view.kind === "checking" || view.kind === "approved"
                ? view.photo
                : null;
            const index = photo ? grid.live.indexOf(photo) : -1;
            return (
              <PhotoSlot
                key={slotKey(view, place)}
                view={view}
                place={place}
                busy={grid.busy}
                locked={locked}
                first={index === 0}
                last={index === grid.live.length - 1}
                onChoose={() =>
                  choose(view.kind === "empty" ? firstFree : place)
                }
                onRetry={() => grid.retry(place)}
                onDismiss={() => grid.dismiss(place)}
                onRemove={grid.remove}
                onMove={(by) => photo && grid.move(photo.id, by)}
                onDragStart={() => photo && setDragged(photo.id)}
                onDragEnd={() => setDragged(null)}
                onDrop={() => {
                  if (photo && dragged) grid.moveOnto(dragged, photo.id);
                  setDragged(null);
                }}
              />
            );
          })}
        </ol>
      ) : grid.photos.isError ? (
        <ErrorState
          body={t("onboarding.photos.loadFailed")}
          onRetry={() => void grid.photos.refetch()}
        />
      ) : (
        <div aria-busy className="grid grid-cols-3 gap-2.5">
          {Array.from({ length: PHOTO_SLOTS }, (_, n) => (
            <Skeleton key={n} className="rounded-input aspect-[3/4]" />
          ))}
        </div>
      )}
    </>
  );
}
