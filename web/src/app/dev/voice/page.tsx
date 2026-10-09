import { notFound } from "next/navigation";

import { VoiceHarness } from "./VoiceHarness";

/**
 * P-520's recordings (T-7.11): the app's own recorder (`voice-recorder.ts`),
 * saved as a file named for the browser and the recorder's measured length,
 * so `api/tests/core/test_audio_recordings.py` can hold the server's measuring
 * to it. Same allowlist as `/dev/ui`: only `next dev` serves it. No `metadata`
 * export, and its copy inline, as dev pages' is.
 */
export default function DevVoicePage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <VoiceHarness />;
}
