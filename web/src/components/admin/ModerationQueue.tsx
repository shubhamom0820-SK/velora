"use client";

import { t } from "@/i18n/t";
import { useAdminModeration } from "@/lib/queries/admin";

import { AdminList } from "./AdminList";
import { PhotoCard } from "./PhotoCard";

/**
 * The moderation queue (T-9.5, D-925): pending public and private photos,
 * oldest first, never a selfie or the face photo. One the worker couldn't
 * decide, its scores missing, waits here for a person.
 */
export function ModerationQueue() {
  const photos = useAdminModeration();
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.photos.title")}</h1>
      <AdminList
        query={photos}
        empty={t("admin.photos.empty")}
        keyOf={(photo) => photo.id}
      >
        {(photo) => <PhotoCard photo={photo} />}
      </AdminList>
    </section>
  );
}
