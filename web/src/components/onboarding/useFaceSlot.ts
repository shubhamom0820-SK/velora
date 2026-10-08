"use client";

import { useEffect, useRef, useState } from "react";

import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import {
  facePhoto,
  shownCopy,
  useDeletePhoto,
  useMyPhotos,
  usePhotoOutcomes,
  useShowFacePhoto,
  useUploadFacePhoto,
  type Photo,
} from "@/lib/queries/photos";
import { resizeForUpload } from "@/lib/resize-image";

import { errorCopy } from "./errorCopy";
import { isRefusal, reasonCopy, uploadErrorCopy } from "./photoCopy";

/** What the face slot shows (T-4.12): the grid's states, for one place. */
export type FaceView =
  | { kind: "empty" }
  | { kind: "uploading"; percent: number; preview: string | null }
  | { kind: "checking"; photo: Photo; preview: string | null }
  | { kind: "approved"; photo: Photo; preview: string | null }
  | { kind: "rejected"; copy: string }
  | { kind: "failed"; copy: string; preview: string | null };

type Local =
  | { kind: "uploading"; percent: number; preview: string | null }
  | { kind: "failed"; copy: string; preview: string | null; body: Blob }
  | { kind: "rejected"; copy: string };

/**
 * The face photo's slot (T-4.12, D-391): the one the selfie is compared
 * with, uploaded as kind `verification`, one live per person. Its states are
 * the grid's (`usePhotoSlots`), for one place: what the API lists, and what
 * this page alone knows, an upload under way and why a photo isn't there. A
 * face photo seen checking that leaves the list is read once (D-096) so the
 * slot can say why; one the API `replaced` just leaves. The toggle is the
 * public copy's presence (`from_photo_id`), so a reload shows it as it is.
 */
export function useFaceSlot() {
  const photos = useMyPhotos();
  const { mutateAsync: upload } = useUploadFacePhoto();
  const show = useShowFacePhoto();
  const hide = useDeletePhoto();
  const [local, setLocal] = useState<Local | null>(null);
  const [watched, setWatched] = useState<string | null>(null);
  const [vanished, setVanished] = useState<string | null>(null);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const created = useRef<Set<string>>(new Set());

  const face = facePhoto(photos.data ?? []);
  const listed = photos.data !== undefined;

  // The list changed: a face photo seen checking that is no longer listed
  // has vanished; a live one clears what the page last said.
  if (listed) {
    const now = face?.status === "pending" ? face.id : null;
    if (watched !== now) {
      if (watched && !face) setVanished(watched);
      setWatched(now);
    }
    if (face && local && local.kind !== "uploading") setLocal(null);
  }
  const [outcome] = usePhotoOutcomes(vanished ? [vanished] : []);
  if (vanished && outcome && (outcome.data || outcome.isError)) {
    const ended = outcome.data;
    setVanished(null);
    if (
      ended?.status === "rejected" &&
      ended.reject_reason !== "user_deleted" &&
      ended.reject_reason !== "replaced" &&
      !face &&
      !local
    ) {
      setLocal({ kind: "rejected", copy: reasonCopy(ended.reject_reason) });
    }
  }

  useEffect(() => {
    const urls = created.current;
    return () => {
      for (const url of urls) URL.revokeObjectURL(url);
    };
  }, []);

  async function send(body: Blob, preview: string | null) {
    setLocal({ kind: "uploading", percent: 0, preview });
    try {
      const photo = await upload({
        body,
        onProgress: (percent) =>
          setLocal((current) =>
            current?.kind === "uploading" ? { ...current, percent } : current,
          ),
      });
      setLocal(null);
      if (preview) setPreviews((all) => ({ ...all, [photo.id]: preview }));
    } catch (error) {
      setLocal(
        isRefusal(error)
          ? { kind: "rejected", copy: uploadErrorCopy(error) }
          : { kind: "failed", copy: uploadErrorCopy(error), preview, body },
      );
    }
  }

  /** Resize what was picked (falling back to the file as it is), then send it. */
  async function add(file: File) {
    setLocal({ kind: "uploading", percent: 0, preview: null });
    const resized = await resizeForUpload(file);
    let preview: string | null = null;
    if (resized) {
      preview = URL.createObjectURL(resized);
      created.current.add(preview);
    }
    await send(resized ?? file, preview);
  }

  function retry() {
    if (local?.kind === "failed") void send(local.body, local.preview);
  }

  const copy = face ? shownCopy(photos.data ?? [], face.id) : null;

  /** The toggle: on makes the public copy, off takes it down. */
  function setShown(on: boolean) {
    if (!face) return;
    if (on) show.mutate(face.id);
    else if (copy) hide.mutate(copy.id);
  }

  let view: FaceView;
  if (local?.kind === "uploading") view = local;
  else if (face) {
    const preview = previews[face.id] ?? null;
    view =
      face.status === "approved"
        ? { kind: "approved", photo: face, preview }
        : { kind: "checking", photo: face, preview };
  } else if (local?.kind === "failed") {
    view = { kind: "failed", copy: local.copy, preview: local.preview };
  } else view = local ?? { kind: "empty" };

  return {
    photos,
    view,
    /** A live face photo, pending or approved: enough to leave the step. */
    hasOne: face !== null,
    add,
    retry,
    dismiss: () => setLocal(null),
    /** The toggle's state: a live public copy of the face photo. */
    shown: copy !== null,
    setShown,
    toggling: show.isPending || hide.isPending,
    /** Why the toggle was refused (no room, not approved yet), until the next try. */
    toggleCopy: toggleCopy(show.error ?? hide.error),
  };
}

/**
 * The toggle's refusal, in the web's words (never the API's, T-3.11):
 * `NOT_ALLOWED` with the places' `max` is no free place; without it, the
 * face photo isn't approved yet. Anything else is the shared wording.
 */
function toggleCopy(error: unknown): string | null {
  if (!error) return null;
  if (error instanceof ApiError && error.code === "NOT_ALLOWED") {
    return typeof error.details?.max === "number"
      ? t("onboarding.photos.face.noRoom")
      : t("onboarding.photos.face.notYet");
  }
  return errorCopy(error).message;
}
