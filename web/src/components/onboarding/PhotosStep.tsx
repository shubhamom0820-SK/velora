"use client";

import { Images } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useFinishPhotos } from "@/lib/queries/photos";

import { errorCopy } from "./errorCopy";
import { FaceSlot } from "./FaceSlot";
import { FormError } from "./FormError";
import { PhotoSlot } from "./PhotoSlot";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";
import { useFaceSlot } from "./useFaceSlot";
import { PHOTO_SLOTS, usePhotoSlots, type SlotView } from "./usePhotoSlots";

/**
 * Who may leave the photos step with no face photo: men only (D-391, D-008).
 * An allowlist, as the selfie step's "Skip for now" is; the server holds the
 * same rule (`FACE_PHOTO_REQUIRED`), whatever this screen shows.
 */
const MAY_LEAVE_WITHOUT_A_FACE_PHOTO: ReadonlySet<Me["gender"]> = new Set([
  "male",
]);

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
 * Photos (T-4.6), the `photos` step: six slots, as the prototype's. Tapping an
 * empty one opens the picker, never forcing the camera, and the photo goes in
 * the first free place, so the places run 0 onwards. From T-4.12 (D-392)
 * nobody needs a public photo, and none needs to show a face: the step is left
 * by `POST /me/photos/done`, which a woman may call once her face photo
 * (D-391, the slot below the grid) is there, pending or approved.
 */
export function PhotosStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const grid = usePhotoSlots();
  const face = useFaceSlot();
  const finish = useFinishPhotos();
  const picker = useRef<HTMLInputElement>(null);
  const target = useRef<number | null>(null);
  const [dragged, setDragged] = useState<string | null>(null);
  const failure = finish.error ?? grid.error;
  const copy = failure ? errorCopy(failure) : null;
  const optional = MAY_LEAVE_WITHOUT_A_FACE_PHOTO.has(me.gender);
  const mayGo = optional || face.hasOne;
  const firstFree = grid.slots.findIndex((slot) => slot.kind === "empty");
  // A delete or reorder is rewriting places: an upload can't pick one now.
  const locked = grid.busy && !grid.uploading;

  function choose(place: number) {
    target.current = place;
    picker.current?.click();
  }

  return (
    <StepFrame
      index={9}
      title={t("onboarding.photos.title")}
      sub={t("onboarding.photos.sub")}
      back={stepPath("about")}
      signedIn
      footer={
        <Button
          fullWidth
          disabled={!mayGo || grid.busy}
          loading={finish.isPending}
          onClick={() => finish.mutate(undefined, { onSuccess: advance })}
        >
          {mayGo
            ? t("onboarding.continue")
            : t("onboarding.photos.face.needOne")}
        </Button>
      }
    >
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
      {grid.photos.data && (
        <FaceSlot slot={face} optional={optional} locked={me.is_verified} />
      )}
      <FormError copy={copy} />
      {me.gender === "female" && (
        <div className="rounded-input bg-surface mt-4 flex items-start gap-2 p-3.5">
          <Icon icon={Images} size={15} className="text-accent mt-0.5" />
          <p className="text-small text-mute">
            {t("onboarding.photos.privateAlbum")}
          </p>
        </div>
      )}
    </StepFrame>
  );
}
