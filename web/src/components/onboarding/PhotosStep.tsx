"use client";

import { Images } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useFinishPhotos } from "@/lib/queries/photos";

import { errorCopy } from "./errorCopy";
import { FaceSlot } from "./FaceSlot";
import { FormError } from "./FormError";
import { PhotoGrid } from "./PhotoGrid";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";
import { useFaceSlot } from "./useFaceSlot";
import { usePhotoSlots } from "./usePhotoSlots";

/**
 * Who may leave the photos step with no face photo: men only (D-391, D-008).
 * An allowlist, as the selfie step's "Skip for now" is; the server holds the
 * same rule (`FACE_PHOTO_REQUIRED`), whatever this screen shows.
 */
const MAY_LEAVE_WITHOUT_A_FACE_PHOTO: ReadonlySet<Me["gender"]> = new Set([
  "male",
]);

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
  const failure = finish.error ?? grid.error;
  const copy = failure ? errorCopy(failure) : null;
  const optional = MAY_LEAVE_WITHOUT_A_FACE_PHOTO.has(me.gender);
  const mayGo = optional || face.hasOne;

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
      <PhotoGrid grid={grid} />
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
