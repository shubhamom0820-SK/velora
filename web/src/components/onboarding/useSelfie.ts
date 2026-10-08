"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import type { CameraFailure } from "@/lib/camera";
import { creditsCount } from "@/lib/credits";
import { queryKeys } from "@/lib/queries/keys";
import { useCompleteOnboarding } from "@/lib/queries/onboarding";
import {
  isBeingCompared,
  useLatestVerification,
  useStartVerification,
  useSubmitSelfie,
  useUploadSelfie,
  VERIFICATION_POLL_FOR_MS,
  type Verification,
} from "@/lib/queries/verification";

import { finishCopy, refusalCopy, sendFailedCopy } from "./selfieCopy";
import { useAdvance } from "./useAdvance";

/**
 * After this long being compared, the screen says it can take a minute and
 * the person can leave (D-261, the founder's constraint on T-4.5): the wake
 * usually decides a selfie within seconds, and the queue within D-091's 10.
 */
export const COMPARING_LONG_MS = 15_000;

/** What the selfie step shows (T-4.7). */
export type SelfieView =
  | { kind: "loading" }
  /** The latest verification couldn't be read. */
  | { kind: "failed" }
  /** Ready to start: nothing yet, or the last selfie rejected, with why. */
  | { kind: "intro"; last: Verification | null }
  | { kind: "camera" }
  | { kind: "cameraFailed"; failure: CameraFailure }
  /** Taken, not sent: use it or take another (T-4.7's plan, question 2). */
  | { kind: "review"; preview: string }
  | { kind: "sending"; preview: string; percent: number }
  | { kind: "sendFailed"; preview: string; copy: string }
  | {
      kind: "comparing";
      preview: string | null;
      /** Past `COMPARING_LONG_MS`: she may leave. */
      long: boolean;
      /** Past `VERIFICATION_POLL_FOR_MS`: no longer asked; "Check again". */
      stopped: boolean;
    }
  | { kind: "matched"; preview: string | null };

/** What this page knows that the API doesn't. */
type Local =
  | { kind: "idle" }
  | { kind: "camera" }
  | { kind: "cameraFailed"; failure: CameraFailure }
  | { kind: "review"; shot: Blob; preview: string }
  | { kind: "sending"; shot: Blob; preview: string; percent: number }
  | { kind: "sendFailed"; shot: Blob; preview: string; copy: string };

/**
 * The selfie step's flow (T-4.7): start the verification, open the camera,
 * take a frame, check it, send it (upload as `kind=selfie`, then submit), and
 * follow `GET /verification/latest` every 2 s while it's compared, for at most
 * a minute at a time. Then finish sign-up (T-4.8). Whether a selfie matched,
 * and whether sign-up may finish, are the server's alone (D-082).
 */
export function useSelfie({ alreadyMatched }: { alreadyMatched: boolean }) {
  const queryClient = useQueryClient();
  const [local, setLocal] = useState<Local>({ kind: "idle" });
  // A refusal to start or send, said on the intro.
  const [notice, setNotice] = useState<string | null>(null);
  // The selfie this page sent, shown while it's compared and once it matches.
  const [sent, setSent] = useState<string | null>(null);
  // Each "Check again" starts another minute of asking.
  const [round, setRound] = useState(0);
  const [longFor, setLongFor] = useState<string | null>(null);
  const [stoppedFor, setStoppedFor] = useState<string | null>(null);
  // Every preview URL this page made, let go of when it closes.
  const created = useRef<Set<string>>(new Set());

  const start = useStartVerification();
  const upload = useUploadSelfie();
  const submit = useSubmitSelfie();
  const complete = useCompleteOnboarding();
  const advance = useAdvance();
  const toast = useToast();

  // The minute of asking is counted per selfie being compared, per round:
  // asked until that round's minute is up.
  const keyOf = (verification: Verification | null) =>
    verification && isBeingCompared(verification)
      ? `${verification.id}:${round}`
      : null;
  const cached = queryClient.getQueryData<Verification | null>(
    queryKeys.verificationLatest(),
  );
  const latest = useLatestVerification({
    poll: stoppedFor === null || stoppedFor !== keyOf(cached ?? null),
  });
  const last = latest.data ?? null;
  const roundKey = keyOf(last);

  useEffect(() => {
    if (!roundKey) return;
    const long = setTimeout(() => setLongFor(roundKey), COMPARING_LONG_MS);
    const stop = setTimeout(
      () => setStoppedFor(roundKey),
      VERIFICATION_POLL_FOR_MS,
    );
    return () => {
      clearTimeout(long);
      clearTimeout(stop);
    };
  }, [roundKey]);

  // A match changes `Me` (`is_verified`), read afresh once.
  const approvedId = last?.status === "approved" ? last.id : null;
  useEffect(() => {
    if (approvedId)
      void queryClient.invalidateQueries({ queryKey: queryKeys.me() });
  }, [approvedId, queryClient]);

  useEffect(() => {
    const urls = created.current;
    return () => {
      for (const url of urls) URL.revokeObjectURL(url);
    };
  }, []);

  function forget(preview: string) {
    URL.revokeObjectURL(preview);
    created.current.delete(preview);
  }

  /** Start (or reopen) the verification, then open the camera. */
  async function openCamera() {
    setNotice(null);
    complete.reset();
    try {
      await start.mutateAsync();
      setLocal({ kind: "camera" });
    } catch (error) {
      // Matched already, or being compared: the latest says which.
      if (error instanceof ApiError && error.code === "NOT_ALLOWED") {
        await latest.refetch();
        return;
      }
      setNotice(refusalCopy(error));
    }
  }

  function capture(shot: Blob) {
    const preview = URL.createObjectURL(shot);
    created.current.add(preview);
    setLocal({ kind: "review", shot, preview });
  }

  /** Another go at the camera: the picture taken is dropped, never sent. */
  function retake() {
    if ("preview" in local) forget(local.preview);
    setLocal({ kind: "camera" });
  }

  function cancel() {
    if ("preview" in local) forget(local.preview);
    setLocal({ kind: "idle" });
  }

  /** The verification waiting for this selfie: the one started, or a new one. */
  async function openVerification(): Promise<string> {
    const current =
      queryClient.getQueryData<Verification | null>(
        queryKeys.verificationLatest(),
      ) ?? null;
    if (current?.status === "pending" && !current.submitted) return current.id;
    return (await start.mutateAsync()).id;
  }

  /** Upload the selfie, then send it to the verification: one of today's tries. */
  async function send(shot: Blob, preview: string) {
    setLocal({ kind: "sending", shot, preview, percent: 0 });
    try {
      const verificationId = await openVerification();
      const photo = await upload.mutateAsync({
        body: shot,
        onProgress: (percent) =>
          setLocal((current) =>
            current.kind === "sending" ? { ...current, percent } : current,
          ),
      });
      await submit.mutateAsync({ verificationId, photoId: photo.id });
      setSent(preview);
      setRound(0);
      setLocal({ kind: "idle" });
    } catch (error) {
      if (
        error instanceof ApiError &&
        ["RATE_LIMITED", "NOT_ALLOWED", "NOT_FOUND"].includes(error.code)
      ) {
        // Today's tries are used, or the verification moved on (matched,
        // being compared, or another tab sent one): the intro, or whatever
        // the latest now says, with why.
        forget(preview);
        setNotice(refusalCopy(error));
        setLocal({ kind: "idle" });
        await latest.refetch();
        return;
      }
      setLocal({
        kind: "sendFailed",
        shot,
        preview,
        copy: sendFailedCopy(error),
      });
    }
  }

  function use() {
    if (local.kind === "review" || local.kind === "sendFailed")
      void send(local.shot, local.preview);
  }

  /** Another minute of asking, now. */
  function checkAgain() {
    setRound((n) => n + 1);
    void latest.refetch();
  }

  /**
   * "Continue" after a match, or a man's "Skip for now": the server finishes
   * sign-up and the person goes where its `Me` says, the app; or it says what
   * is still needed, shown with the way back (T-4.8). A balance on finishing
   * is a new man's welcome Velas (T-8.11, D-470): nothing else can credit him
   * before `done`, so the toast says what the server gave, or nothing.
   */
  function finish() {
    complete.mutate(undefined, {
      onSuccess: (me) => {
        if (me.balance > 0) {
          toast.show({
            message: t(
              me.balance === 1
                ? "onboarding.selfie.welcome.one"
                : "onboarding.selfie.welcome.other",
              { count: creditsCount(me.balance) },
            ),
          });
        }
        advance(me);
      },
      onError: (error) => {
        // The server knows of no match: `Me` and the latest say what it has.
        if (
          error instanceof ApiError &&
          error.code === "VERIFICATION_REQUIRED"
        ) {
          void queryClient.invalidateQueries({ queryKey: queryKeys.me() });
          void latest.refetch();
        }
      },
    });
  }

  let view: SelfieView;
  if (alreadyMatched || last?.status === "approved")
    view = { kind: "matched", preview: sent };
  else if (latest.isPending) view = { kind: "loading" };
  else if (latest.isError) view = { kind: "failed" };
  else if (roundKey)
    view = {
      kind: "comparing",
      preview: sent,
      long: longFor === roundKey || round > 0,
      stopped: stoppedFor === roundKey,
    };
  else if (local.kind === "camera") view = { kind: "camera" };
  else if (local.kind === "cameraFailed")
    view = { kind: "cameraFailed", failure: local.failure };
  else if (local.kind === "review")
    view = { kind: "review", preview: local.preview };
  else if (local.kind === "sending")
    view = { kind: "sending", preview: local.preview, percent: local.percent };
  else if (local.kind === "sendFailed")
    view = { kind: "sendFailed", preview: local.preview, copy: local.copy };
  else view = { kind: "intro", last };

  return {
    view,
    notice,
    starting: start.isPending,
    openCamera,
    cameraFailed: (failure: CameraFailure) =>
      setLocal({ kind: "cameraFailed", failure }),
    /** The camera again, once the person has allowed it. */
    retryCamera: () => setLocal({ kind: "camera" }),
    capture,
    retake,
    cancel,
    use,
    checkAgain,
    retryLoad: () => void latest.refetch(),
    finish,
    finishing: complete.isPending,
    /** Why finishing was refused, until the next try. */
    finishFailure: complete.error ? finishCopy(complete.error) : null,
  };
}
