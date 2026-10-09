"use client";

import { errorCopy } from "@/components/onboarding/errorCopy";
import { FaceSlot } from "@/components/onboarding/FaceSlot";
import { FormError } from "@/components/onboarding/FormError";
import { PhotoGrid } from "@/components/onboarding/PhotoGrid";
import { useFaceSlot } from "@/components/onboarding/useFaceSlot";
import { usePhotoSlots } from "@/components/onboarding/usePhotoSlots";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { type Me, useMe } from "@/lib/queries/me";

/** Your photos (T-9.8), at `/you/photos`. */
export function MyPhotos() {
  const me = useMe();
  return (
    <div className="text-ink flex flex-1 flex-col gap-3 p-(--shell-gutter) pb-8">
      <h1 className="text-title-1">{t("you.photos")}</h1>
      {me.isPending ? (
        <Skeleton className="h-40" />
      ) : me.isError ? (
        <ErrorState onRetry={() => void me.refetch()} />
      ) : (
        <Photos me={me.data} />
      )}
    </div>
  );
}

/**
 * The photos step's grid and face slot (T-4.6, T-4.12), without its frame or
 * its way on: nothing here calls `/me/photos/done`. A new photo goes through
 * moderation as any upload does, and carries no badge until it matches the
 * selfie (D-910). Once the selfie matched, the face photo's slot is locked,
 * as the server refuses a change anyway (T-4.12).
 */
function Photos({ me }: { me: Me }) {
  const grid = usePhotoSlots();
  const face = useFaceSlot();
  const copy = grid.error ? errorCopy(grid.error) : null;
  return (
    <>
      <p className="text-small text-mute">{t("you.photosHint")}</p>
      <PhotoGrid grid={grid} />
      {grid.photos.data && (
        <FaceSlot
          slot={face}
          optional={me.gender === "male"}
          locked={me.is_verified}
        />
      )}
      <FormError copy={copy} />
    </>
  );
}
