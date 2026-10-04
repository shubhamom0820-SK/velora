"use client";

import { useEffect, useRef, useState } from "react";

import {
  publicPhotos,
  useClosePhotoGaps,
  useDeletePhoto,
  useMyPhotos,
  usePhotoOutcomes,
  useReorderPhotos,
  useUploadPhoto,
  type Photo,
} from "@/lib/queries/photos";
import { resizeForUpload } from "@/lib/resize-image";

import { isRefusal, reasonCopy, uploadErrorCopy } from "./photoCopy";

/** Six public places; 0 is the main photo (T-4.2, 03-SCHEMA). */
export const PHOTO_SLOTS = 6;

/** What a slot shows (T-4.6): each state the plan names, and an empty place. */
export type SlotView =
  | { kind: "empty" }
  /** On its way up; at 100, the server is checking what arrived. */
  | { kind: "uploading"; percent: number; preview: string | null }
  /** Uploaded, and waiting for moderation (pending). */
  | { kind: "checking"; photo: Photo; preview: string | null }
  | { kind: "approved"; photo: Photo; preview: string | null }
  /** The server said no: the file (D-089), or moderation (D-096). */
  | { kind: "rejected"; copy: string }
  /** It didn't get there: tried again with the same photo. */
  | { kind: "failed"; copy: string; preview: string | null };

/** What this page knows that `GET /me/photos` doesn't list, by place. */
type Local =
  | { kind: "uploading"; percent: number; preview: string | null }
  | { kind: "failed"; copy: string; preview: string | null; body: Blob }
  | { kind: "rejected"; copy: string };

type State = {
  /** The list as last seen, to tell which photos have left it. */
  listed: readonly Photo[] | undefined;
  /** Photos seen being checked: their places, as last listed. */
  watched: Readonly<Record<string, number>>;
  /** Photos that left the list while being checked, until their ending is known. */
  vanished: Readonly<Record<string, number>>;
  local: Readonly<Record<number, Local>>;
  /** This page's own previews of what it uploaded, by photo id. */
  previews: Readonly<Record<string, string>>;
};

const INITIAL: State = {
  listed: undefined,
  watched: {},
  vanished: {},
  local: {},
  previews: {},
};

function without<V>(
  record: Readonly<Record<string | number, V>>,
  key: string | number,
): Record<string, V> {
  return Object.fromEntries(
    Object.entries(record).filter(([k]) => k !== String(key)),
  );
}

/**
 * A new list: every photo it no longer holds that was being checked has
 * vanished (rejected, most likely), and a photo now in a place clears what the
 * page last said there.
 */
function observe(state: State, listed: readonly Photo[] | undefined): State {
  if (!listed) return { ...state, listed };
  const live = publicPhotos(listed);
  const ids = new Set(live.map((photo) => photo.id));
  const vanished = { ...state.vanished };
  for (const [id, place] of Object.entries(state.watched)) {
    if (!ids.has(id)) vanished[id] = place;
  }
  const watched: Record<string, number> = {};
  for (const photo of live) {
    if (photo.status === "pending" && photo.position !== null) {
      watched[photo.id] = photo.position;
    }
  }
  const taken = new Set(live.map((photo) => photo.position));
  const local = Object.fromEntries(
    Object.entries(state.local).filter(
      ([place, here]) => here.kind === "uploading" || !taken.has(Number(place)),
    ),
  );
  return { ...state, listed, watched, vanished, local };
}

/**
 * How vanished photos ended: a rejection is said in the slot that showed it,
 * unless something else is there now. A photo the person removed (here or in
 * another tab) just leaves.
 */
/** A vanished photo and how it ended: null if that couldn't be read. */
type Ending = readonly [string, Photo | null];

function settle(state: State, endings: readonly Ending[]): State {
  let { vanished, local } = state;
  const taken = new Set(
    publicPhotos(state.listed ?? []).map((photo) => photo.position),
  );
  for (const [id, photo] of endings) {
    const place = vanished[id];
    vanished = without(vanished, id);
    if (
      place === undefined ||
      photo?.status !== "rejected" ||
      photo.reject_reason === "user_deleted" ||
      local[place] ||
      taken.has(place)
    ) {
      continue;
    }
    local = {
      ...local,
      [place]: { kind: "rejected", copy: reasonCopy(photo.reject_reason) },
    };
  }
  return { ...state, vanished, local };
}

/**
 * The photos step's six slots (T-4.6): the API's live photos by place, and
 * what this page alone knows, uploads under way and why a photo isn't there.
 */
export function usePhotoSlots() {
  const photos = useMyPhotos();
  const { mutateAsync: uploadPhoto } = useUploadPhoto();
  const remove = useDeletePhoto();
  const reorder = useReorderPhotos();
  const closeGaps = useClosePhotoGaps();
  const [state, setState] = useState<State>(INITIAL);
  // Every preview URL this page made, let go of when it closes.
  const created = useRef<Set<string>>(new Set());

  // Each new list is compared with the last one as it renders, React's way of
  // adjusting state to new data without an effect.
  if (photos.data !== state.listed) {
    setState((current) => observe(current, photos.data));
  }
  const vanishedIds = Object.keys(state.vanished);
  const outcomes = usePhotoOutcomes(vanishedIds);
  const endings = vanishedIds.flatMap((id, n): Ending[] => {
    const outcome = outcomes[n];
    if (outcome?.data) return [[id, outcome.data]];
    if (outcome?.isError) return [[id, null]];
    return [];
  });
  if (endings.length > 0) {
    setState((current) => settle(current, endings));
  }

  useEffect(() => {
    const urls = created.current;
    return () => {
      for (const url of urls) URL.revokeObjectURL(url);
    };
  }, []);

  function setLocal(place: number, next: Local | null) {
    setState((current) => ({
      ...current,
      local: next
        ? { ...current.local, [place]: next }
        : without(current.local, place),
    }));
  }

  async function send(place: number, body: Blob, preview: string | null) {
    setLocal(place, { kind: "uploading", percent: 0, preview });
    try {
      const photo = await uploadPhoto({
        body,
        position: place,
        onProgress: (percent) =>
          setState((current) => {
            const here = current.local[place];
            if (here?.kind !== "uploading") return current;
            return {
              ...current,
              local: { ...current.local, [place]: { ...here, percent } },
            };
          }),
      });
      setState((current) => ({
        ...current,
        local: without(current.local, place),
        previews: preview
          ? { ...current.previews, [photo.id]: preview }
          : current.previews,
      }));
    } catch (error) {
      setLocal(
        place,
        isRefusal(error)
          ? { kind: "rejected", copy: uploadErrorCopy(error) }
          : { kind: "failed", copy: uploadErrorCopy(error), preview, body },
      );
    }
  }

  /** Resize what was picked (falling back to the file as it is), then send it. */
  async function add(place: number, file: File) {
    setLocal(place, { kind: "uploading", percent: 0, preview: null });
    const resized = await resizeForUpload(file);
    let preview: string | null = null;
    if (resized) {
      preview = URL.createObjectURL(resized);
      created.current.add(preview);
    }
    await send(place, resized ?? file, preview);
  }

  function retry(place: number) {
    const here = state.local[place];
    if (here?.kind === "failed") void send(place, here.body, here.preview);
  }

  /** Clear what a slot says, then close the gap, if one is left. */
  function dismiss(place: number) {
    setLocal(place, null);
    closeGaps.mutate();
  }

  const live = publicPhotos(photos.data ?? []);
  const order = live.map((photo) => photo.id);

  function move(id: string, by: -1 | 1) {
    const from = order.indexOf(id);
    const to = from + by;
    if (from < 0 || to < 0 || to >= order.length) return;
    const next = [...order];
    [next[from], next[to]] = [next[to] as string, next[from] as string];
    reorder.mutate(next);
  }

  /** Drag and drop: `id` takes `target`'s place, the rest move along. */
  function moveOnto(id: string, target: string) {
    const from = order.indexOf(id);
    const to = order.indexOf(target);
    if (from < 0 || to < 0 || from === to) return;
    const next = order.filter((other) => other !== id);
    next.splice(to, 0, id);
    reorder.mutate(next);
  }

  const slots: SlotView[] = Array.from({ length: PHOTO_SLOTS }, (_, place) => {
    const here = state.local[place];
    if (here?.kind === "uploading") return here;
    const photo = live.find((listed) => listed.position === place);
    if (photo) {
      const preview = state.previews[photo.id] ?? null;
      return photo.status === "approved"
        ? { kind: "approved", photo, preview }
        : { kind: "checking", photo, preview };
    }
    if (here?.kind === "failed") {
      return { kind: "failed", copy: here.copy, preview: here.preview };
    }
    return here ?? { kind: "empty" };
  });

  const uploading = slots.some((slot) => slot.kind === "uploading");
  return {
    photos,
    slots,
    live,
    /** While anything moves photos about, nothing else may. */
    busy: uploading || remove.isPending || reorder.isPending,
    uploading,
    /** A failed delete or reorder, said under the grid. */
    error: remove.error ?? reorder.error ?? closeGaps.error,
    add,
    retry,
    dismiss,
    remove: (photo: Photo) => remove.mutate(photo.id),
    move,
    moveOnto,
  };
}
