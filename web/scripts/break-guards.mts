/**
 * Breaking runs for the web (T-4.6), as `api/tests/break_guards.py` is for the
 * API: each guard weakened on purpose, one at a time, to prove a test goes red
 * when it is gone (the proof standard, 06-TESTING).
 *
 *   node scripts/break-guards.mts            # every case, once (from web/)
 *   node scripts/break-guards.mts t46-csp    # cases by id prefix
 *
 * Each case edits one file as a careless change would, runs the vitest files
 * it names, and puts the file back byte for byte, proved by SHA-256 before the
 * next case. A case is red only when the run failed and every test it expects
 * failed with it. If the process is killed mid-case, `git status` shows the
 * weakened file and `git checkout -- <file>` restores it.
 * `src/lib/break-guards.test.ts` keeps every case's anchor honest.
 */

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export type BreakCase = {
  id: string;
  /** The file weakened, under web/. */
  file: string;
  old: string;
  new: string;
  /** The vitest files run. */
  run: string[];
  /** Tests that must fail, matched within their names. */
  expect: string[];
};

const CSP_TEST = "src/lib/security-headers.test.ts";
const STORAGE_TEST = "src/lib/storage-origins.test.ts";
const STEP_TEST = "src/components/onboarding/PhotosStep.test.tsx";
const UPLOAD_TEST = "src/lib/upload.test.ts";
const HOOKS_TEST = "src/lib/queries/photos.test.tsx";
const LINT_TEST = "src/lib/no-fetch-rule.test.ts";
const CLAIMS_TEST = "src/i18n/claims.test.ts";
const SELFIE_TEST = "src/components/onboarding/SelfieStep.test.tsx";
const CAMERA_TEST = "src/lib/camera.test.ts";
const VERIFICATION_TEST = "src/lib/queries/verification.test.tsx";
const SEARCH_TEST = "src/components/search/SearchScreen.test.tsx";
const PROXY_TEST = "src/proxy.test.ts";
const DECK_TEST = "src/components/discover/DiscoverScreen.test.tsx";
const PROVIDER_TEST = "src/lib/queries/QueryProvider.test.tsx";
const DECK = "src/components/discover/DiscoverScreen.tsx";
const FILTERS_TEST = "src/components/discover/FiltersSheet.test.tsx";
const FILTERS_SHEET = "src/components/discover/FiltersSheet.tsx";
const FILTER_PARAMS = "src/components/discover/filterParams.ts";
const SHEET_TEST = "src/components/ui/Sheet.test.tsx";
const CHATS = "src/components/chats/ChatsScreen.tsx";
const CHATS_TEST = "src/components/chats/ChatsScreen.test.tsx";
const THREADS_HOOKS = "src/lib/queries/threads.ts";
const THREADS_HOOKS_TEST = "src/lib/queries/threads.test.tsx";
const TICKER = "src/lib/ticker.ts";
const TICKER_TEST = "src/lib/ticker.test.ts";
const COUNTDOWN = "src/components/ui/Countdown.tsx";
const COUNTDOWN_TEST = "src/components/ui/Countdown.test.tsx";
const HER_ROWS = "draws no countdown and no expired state on her rows";
const ONE_TICKER = "runs one 1 s interval for every reader";
const TAKEN_OUT = "takes the row out at once, then offers Undo";
const COUNTS = "counts one page of each tier";
const ASKS_ALL = "asks the API with every filter in the URL";
const BADGE_COUNTS = "counts each intent and each toggle on the Filters button";
const SHOW_WRITES = "Show people writes the draft to the URL";
const DRAFT = "holds every change as a draft";
const SHOWN =
  "shows Super's price from /prices as a number, and sends exactly it";
const HER_DECK = "shows no price anywhere and sends 0 with her Super Like";
const HIS_THREAD =
  "offers him the Thread at /prices' price and sends exactly it";
const HER_THREAD = "offers her the Thread free, sending 0";
const LIKES_TEST = "src/components/likes/LikedYouScreen.test.tsx";
const PROFILE_TEST = "src/components/profile/ProfileScreen.test.tsx";
const REDIRECT_TEST = "src/components/share/SignedInProfileRedirect.test.tsx";
const SHARE_LAYOUT_TEST = "src/app/(share)/layout.test.ts";
const ROUTES_TEST = "src/app/routes.test.ts";
const STORE_SHEET = "src/components/wallet/StoreSheet.tsx";
const STORE_TEST = "src/components/wallet/StoreSheet.test.tsx";
const PACKS_TEST = "src/components/wallet/PackList.test.tsx";
const STORE_MATH = "src/lib/store-math.ts";
const STORE_MATH_TEST = "src/lib/store-math.test.ts";
const STORE_QUERIES = "src/lib/queries/store.ts";
const STORE_QUERIES_TEST = "src/lib/queries/store.test.tsx";
const CHECKOUT_PATH = "src/lib/checkout-path.ts";
const CHECKOUT_PATH_TEST = "src/lib/checkout-path.test.ts";

const HEADERS = "src/lib/security-headers.ts";
const CONNECT = "connect: ` ${storage.privateBucket}`,";
const IMG = "img: ` blob: ${storage.privateBucket} ${storage.cdn}`,";
const EXACT_LOCAL = "adds exactly the local S3's photo sources";
const EXACT_R2 = "this environment's photo storage (T-4.6) on a Firebase build";

const SCREEN = "src/components/conversation/ConversationScreen.tsx";
const SCREEN_TEST = "src/components/conversation/ConversationScreen.test.tsx";
const COMPOSER_TEST = SCREEN_TEST;
const MIC_TEST = "src/components/conversation/MicButton.test.tsx";

// T-7.12: the socket, its events' caches, the conversation's live parts.
const WS = "src/lib/ws.ts";
const WS_TEST = "src/lib/ws.test.ts";
const REALTIME = "src/lib/queries/realtime.ts";
const REALTIME_TEST = "src/lib/queries/realtime.test.ts";
const CSP712 = "src/lib/security-headers.ts";
const SCREEN712 = "src/components/conversation/ConversationScreen.tsx";
const REPORT_SHEET712 = "src/components/profile/ReportSheet.tsx";
const COMPOSER712 = "src/components/conversation/Composer.tsx";

export const CASES: BreakCase[] = [
  // --- The CSP (D-059): each source removed, then widened ---
  {
    id: "t46-csp-01-upload-bucket-removed",
    file: HEADERS,
    old: CONNECT,
    new: "connect: ``,",
    run: [CSP_TEST],
    expect: [EXACT_LOCAL, EXACT_R2],
  },
  {
    id: "t46-csp-02-blob-removed",
    file: HEADERS,
    old: IMG,
    new: "img: ` ${storage.privateBucket} ${storage.cdn}`,",
    run: [CSP_TEST],
    expect: [EXACT_LOCAL, EXACT_R2],
  },
  {
    id: "t46-csp-03-signed-links-removed",
    file: HEADERS,
    old: IMG,
    new: "img: ` blob: ${storage.cdn}`,",
    run: [CSP_TEST],
    expect: [EXACT_LOCAL, EXACT_R2],
  },
  {
    id: "t46-csp-04-cdn-removed",
    file: HEADERS,
    old: IMG,
    new: "img: ` blob: ${storage.privateBucket}`,",
    run: [CSP_TEST],
    expect: [EXACT_LOCAL, EXACT_R2],
  },
  {
    id: "t46-csp-05-connect-wildcard",
    file: HEADERS,
    old: CONNECT,
    new: "connect: ` https://*.r2.cloudflarestorage.com`,",
    run: [CSP_TEST],
    expect: [EXACT_R2, "never a whole storage endpoint or a wildcard"],
  },
  {
    id: "t46-csp-06-img-wildcard",
    file: HEADERS,
    old: IMG,
    new: "img: ` blob: *`,",
    run: [CSP_TEST],
    expect: [EXACT_LOCAL, "never a whole storage endpoint or a wildcard"],
  },
  {
    id: "t46-csp-07-whole-endpoint",
    file: "src/lib/storage-origins.ts",
    old: "privateBucket: `${R2}/velora-staging-private/`,",
    new: "privateBucket: `${R2}`,",
    run: [STORAGE_TEST, CSP_TEST],
    expect: [
      "APP_ENV=staging names what infra/fly.api.toml signs and serves",
      "never a whole storage endpoint or a wildcard",
    ],
  },
  {
    id: "t46-csp-08-staging-given-production-s-bucket",
    file: "src/lib/storage-origins.ts",
    old: "privateBucket: `${R2}/velora-staging-private/`,",
    new: "privateBucket: `${R2}/velora-prod-private/`,",
    run: [STORAGE_TEST],
    expect: ["never lets one environment's pages reach the other's"],
  },
  {
    id: "t46-csp-09-unknown-app-env-gets-local",
    file: "src/lib/storage-origins.ts",
    old: "return STORAGE_FOR.get(appEnv) ?? null;",
    new: "return STORAGE_FOR.get(appEnv) ?? LOCAL;",
    run: [STORAGE_TEST],
    expect: ["no storage at all"],
  },
  // --- The per-slot states ---
  {
    id: "t46-slot-01-uploading-percent-gone",
    file: "src/components/onboarding/PhotoSlot.tsx",
    old: '{t("onboarding.photos.uploading", { percent: view.percent })}\n                </span>',
    new: '{""}\n                </span>',
    run: [STEP_TEST],
    expect: ["PUTs with exactly the signed headers and progress"],
  },
  {
    id: "t46-slot-02-checking-silent",
    file: "src/components/onboarding/PhotoChecking.tsx",
    old: '{t("onboarding.photos.checking")}',
    new: '{""}',
    run: [STEP_TEST],
    expect: ["shows a pending photo by its signed link, blurred, as checking"],
  },
  {
    id: "t46-slot-03-approved-drawn-as-checking",
    file: "src/components/onboarding/usePhotoSlots.ts",
    old: 'return photo.status === "approved"',
    new: 'return photo.status === "nothing"',
    run: [STEP_TEST],
    expect: ["shows an approved photo plainly"],
  },
  {
    id: "t46-slot-04-rejected-without-reason",
    file: "src/components/onboarding/PhotoSlot.tsx",
    old: "{view.copy}",
    new: "{null}",
    run: [STEP_TEST],
    expect: ["says why in the place it was", "accusing nobody"],
  },
  {
    id: "t46-slot-05-moderation-rejection-never-arrives",
    file: "src/components/onboarding/usePhotoSlots.ts",
    old: "  if (endings.length > 0) {",
    new: "  if (endings.length < 0) {",
    run: [STEP_TEST],
    expect: ["says why in the place it was", "accusing nobody"],
  },
  {
    id: "t46-slot-06-retry-opens-the-picker",
    file: "src/components/onboarding/PhotoSlot.tsx",
    old: 'onClick={view.kind === "rejected" ? onChoose : onRetry}',
    new: "onClick={onChoose}",
    run: [STEP_TEST],
    expect: ["gives the place back when the upload never arrives"],
  },
  {
    id: "t46-slot-07-a-possible-minor-named",
    file: "src/i18n/en.ts",
    old: 'other: "We couldn\'t verify this photo — try a different one",',
    new: 'other: "This photo may show someone under 18 — try a different one",',
    run: [STEP_TEST],
    expect: ["accusing nobody"],
  },
  {
    id: "t46-slot-08-unlisted-reason-shown-by-name",
    file: "src/components/onboarding/photoCopy.ts",
    old: 'REASONS.find((listed) => listed === reason) ?? "other";',
    new: "reason as Reason;",
    run: [STEP_TEST],
    expect: ["reads minor_suspected in D-093's words"],
  },
  // --- The transport boundary (CLAUDE.md rule 14) ---
  {
    id: "t46-lint-01-xhr-allowed-outside-lib",
    file: "eslint.config.mjs",
    old: 'const TRANSPORTS = ["fetch", "XMLHttpRequest", "WebSocket"];',
    new: 'const TRANSPORTS = ["fetch", "WebSocket"];',
    run: [LINT_TEST],
    expect: [
      "flags XMLHttpRequest in src/components/onboarding/PhotosStep.tsx",
    ],
  },
  {
    id: "t46-lint-02-fetch-allowed-outside-lib",
    file: "eslint.config.mjs",
    old: 'const TRANSPORTS = ["fetch", "XMLHttpRequest", "WebSocket"];',
    new: 'const TRANSPORTS = ["XMLHttpRequest", "WebSocket"];',
    run: [LINT_TEST],
    expect: ["flags fetch in src/components/feed/Feed.tsx"],
  },
  // --- The upload ---
  {
    id: "t46-upload-01-an-extra-header",
    file: "src/lib/upload.ts",
    old: "    xhr.withCredentials = false;\n",
    new: '    xhr.withCredentials = false;\n    xhr.setRequestHeader("X-Extra", "1");\n',
    run: [UPLOAD_TEST, STEP_TEST],
    expect: ["exactly the signed headers and no credentials"],
  },
  {
    id: "t46-upload-02-cookies-sent",
    file: "src/lib/upload.ts",
    old: "xhr.withCredentials = false;",
    new: "xhr.withCredentials = true;",
    run: [UPLOAD_TEST],
    expect: ["exactly the signed headers and no credentials"],
  },
  {
    id: "t46-upload-03-no-progress",
    file: "src/lib/upload.ts",
    old: "      if (event.lengthComputable && event.total > 0) {",
    new: "      if (event.lengthComputable && event.total < 0) {",
    run: [UPLOAD_TEST, STEP_TEST],
    expect: ["reports progress as whole percentages"],
  },
  {
    id: "t46-upload-04-a-failed-put-keeps-its-place",
    file: "src/lib/queries/photos.ts",
    old: '    await api\n      .delete("/v1/photos/{photo_id}", { params: { photo_id } })\n      .catch(() => undefined);\n',
    new: "",
    run: [HOOKS_TEST, STEP_TEST],
    expect: ["gives the place back when the PUT fails"],
  },
  {
    id: "t46-upload-05-declared-type-forced",
    file: "src/lib/queries/photos.ts",
    old: "content_type: body.type",
    new: 'content_type: "image/jpeg"',
    run: [HOOKS_TEST, STEP_TEST],
    expect: ["sends a file the browser can't read as it is"],
  },
  {
    id: "t46-upload-06-no-polling",
    file: "src/lib/queries/photos.ts",
    old: "query.state.data?.some(isPending) ? PHOTO_POLL_MS : false",
    new: "false",
    run: [HOOKS_TEST],
    expect: ["asks again while a photo is being checked"],
  },
  {
    id: "t46-upload-07-not-resized",
    file: "src/lib/resize-image.ts",
    old: "  if (longest <= max) return { width, height };",
    new: "  if (longest > 0) return { width, height };",
    run: ["src/lib/resize-image.test.ts"],
    expect: ["draws a large photo at 2000 px"],
  },

  // --- T-4.5: the words claim no more than a selfie compared (D-262) ---
  {
    id: "t45-copy-01-the-badge-says-verified",
    file: "src/i18n/en.ts",
    old: '    selfieMatched: "Selfie matched",',
    new: '    selfieMatched: "Verified",',
    run: [CLAIMS_TEST],
    expect: ["says none of the claims anywhere but the two named keys"],
  },
  {
    id: "t45-copy-02-the-landing-page-says-verification",
    file: "src/i18n/en.ts",
    old: '        body: "Selfies compared with a face photo, and every photo checked.",',
    new: '        body: "Selfie verification, and every photo checked.",',
    run: [CLAIMS_TEST],
    expect: ["says none of the claims anywhere but the two named keys"],
  },
  {
    id: "t45-copy-03-the-team-may-look-softened",
    file: "src/i18n/en.ts",
    old: "Other people on {app} never see it; our team may look at it to check a comparison.",
    new: "Other people on {app} never see it.",
    run: [CLAIMS_TEST],
    expect: ["keeps the sentence that says the team may look"],
  },
  {
    id: "t45-badge-01-a-shield-again",
    file: "src/components/ui/Avatar.tsx",
    old: 'import { Check } from "lucide-react";',
    new: 'import { Shield as Check } from "lucide-react";',
    run: ["src/components/ui/Avatar.test.tsx"],
    expect: ["marks the badge with a tick in the accent, never a shield"],
  },

  // --- T-4.7: the selfie step ---
  {
    id: "t47-camera-01-still-denied",
    file: HEADERS,
    old: '"camera=(self), microphone=(self), geolocation=(self), browsing-topics=()",',
    new: '"camera=(), microphone=(self), geolocation=(self), browsing-topics=()",',
    run: [CSP_TEST],
    expect: ["allow the camera (T-4.7), location (T-4.10)"],
  },
  {
    id: "t47-camera-02-any-site",
    file: HEADERS,
    old: '"camera=(self), microphone=(self), geolocation=(self), browsing-topics=()",',
    new: '"camera=*, microphone=(self), geolocation=(self), browsing-topics=()",',
    run: [CSP_TEST],
    expect: ["allow the camera (T-4.7), location (T-4.10)"],
  },
  {
    id: "t47-camera-03-no-blob-for-the-frame",
    file: HEADERS,
    old: IMG,
    new: "img: ` ${storage.privateBucket} ${storage.cdn}`,",
    run: [CSP_TEST],
    expect: ["keep blob: images wherever a selfie can be taken"],
  },
  {
    id: "t47-camera-04-the-microphone-asked",
    file: "src/lib/camera.ts",
    old: "  audio: false,",
    new: "  audio: true,",
    run: [CAMERA_TEST],
    expect: ["never the microphone"],
  },
  {
    id: "t47-camera-05-the-back-camera",
    file: "src/lib/camera.ts",
    old: '    facingMode: "user",',
    new: '    facingMode: "environment",',
    run: [CAMERA_TEST],
    expect: ["asks for the front camera"],
  },
  {
    id: "t47-camera-06-the-picture-mirrored",
    file: "src/lib/camera.ts",
    old: "  context.drawImage(video, 0, 0, width, height);",
    new: "  context.scale(-1, 1);\n  context.drawImage(video, -width, 0, width, height);",
    run: [CAMERA_TEST],
    expect: ["never mirrored"],
  },
  {
    id: "t47-camera-07-the-preview-not-mirrored",
    file: "src/components/onboarding/SelfieCamera.tsx",
    old: 'className="size-full -scale-x-100 object-cover"',
    new: 'className="size-full object-cover"',
    run: [SELFIE_TEST],
    expect: ["opens the front camera, mirrored"],
  },
  {
    id: "t47-camera-08-left-on",
    file: "src/components/onboarding/SelfieCamera.tsx",
    old: "      closed = true;\n      stopCamera(stream);",
    new: "      closed = true;",
    run: [SELFIE_TEST],
    expect: [
      "switches the camera off on cancel",
      "switches the camera off when the page goes",
      "switches the camera off once the picture is taken",
    ],
  },
  {
    id: "t47-skip-01-a-woman-may-skip",
    file: "src/components/onboarding/SelfieStep.tsx",
    old: 'new Set(["male"]);',
    new: 'new Set(["male", "female"]);',
    run: [SELFIE_TEST],
    expect: ["a woman can't"],
  },
  {
    id: "t47-skip-02-a-man-may-not",
    file: "src/components/onboarding/SelfieStep.tsx",
    old: "const skip = maySkip ? (",
    new: "const skip = false ? (",
    run: [SELFIE_TEST],
    expect: ["a man can", "can skip after a rejection too"],
  },
  {
    id: "t47-review-01-sent-as-soon-as-taken",
    file: "src/components/onboarding/useSelfie.ts",
    old: '    setLocal({ kind: "review", shot, preview });',
    new: "    void send(shot, preview);",
    run: [SELFIE_TEST],
    expect: ["sends nothing yet"],
  },
  {
    id: "t47-poll-01-never-stops",
    file: "src/lib/queries/verification.ts",
    old: "      poll && isBeingCompared(query.state.data ?? null)",
    new: "      isBeingCompared(query.state.data ?? null)",
    run: [SELFIE_TEST, VERIFICATION_TEST],
    expect: ["stops asking after a minute", "being compared, told to stop"],
  },
  {
    id: "t47-poll-02-every-ten-seconds",
    file: "src/lib/queries/verification.ts",
    old: "export const VERIFICATION_POLL_MS = 2_000;",
    new: "export const VERIFICATION_POLL_MS = 10_000;",
    run: [VERIFICATION_TEST],
    expect: ["being compared, asked to poll"],
  },
  {
    id: "t47-poll-03-never-says-she-can-leave",
    file: "src/components/onboarding/useSelfie.ts",
    old: "export const COMPARING_LONG_MS = 15_000;",
    new: "export const COMPARING_LONG_MS = 60_000;",
    run: [SELFIE_TEST],
    expect: ["says after about 15 s"],
  },
  {
    id: "t47-poll-04-none-is-an-error",
    file: "src/lib/queries/verification.ts",
    old: '        if (error instanceof ApiError && error.code === "NOT_FOUND")\n          return null;\n',
    new: "",
    run: [SELFIE_TEST, VERIFICATION_TEST],
    expect: ["reads none (NOT_FOUND) as null", "with none yet"],
  },
  {
    id: "t47-copy-01-a-match-says-verified",
    file: "src/i18n/en.ts",
    old: '      matched: "Your selfie matched your face photo.",',
    new: '      matched: "You\'re verified.",',
    run: [CLAIMS_TEST],
    expect: ["says none of the claims anywhere but the two named keys"],
  },
  {
    id: "t47-copy-02-the-team-may-look-dropped",
    file: "src/i18n/en.ts",
    old: '"Other people on {app} never see your selfie. Our team may look at it to check a comparison.",',
    new: '"Other people on {app} never see your selfie.",',
    run: [CLAIMS_TEST, SELFIE_TEST],
    expect: ["keeps the sentence that says the team may look", "with none yet"],
  },
  {
    id: "t47-reasons-01-an-unlisted-reason-unhandled",
    file: "src/components/onboarding/selfieCopy.ts",
    old: '  const known: Reason = REASONS.find((listed) => listed === reason) ?? "other";',
    new: '  const known = (reason ?? "other") as Reason;',
    run: [SELFIE_TEST],
    expect: ["anything_new"],
  },
  {
    id: "t47-reasons-02-one-tries",
    file: "src/components/onboarding/selfieCopy.ts",
    old: '  if (left === 1) return t("onboarding.selfie.triesOne");\n',
    new: "",
    run: [SELFIE_TEST],
    expect: ["with 1 left"],
  },
  {
    id: "t47-reasons-03-the-wait-unsaid",
    file: "src/components/onboarding/selfieCopy.ts",
    old: '    if (typeof after === "number") return waitCopy(after);\n',
    new: "",
    run: [SELFIE_TEST],
    expect: [
      "says how long to wait",
      "says minutes when the wait is under an hour",
    ],
  },
  // --- T-4.8: the two ways on finish sign-up, and a refusal says why ---
  {
    id: "t48-finish-01-the-server-never-asked",
    file: "src/components/onboarding/useSelfie.ts",
    old: "  function finish() {\n    complete.mutate(",
    new: "  function finish() {\n    return;\n    complete.mutate(",
    run: [SELFIE_TEST],
    expect: [
      "a man can",
      "Continue finishes sign-up",
      "names the first of",
      "can't be asked twice at once",
    ],
  },
  {
    id: "t48-finish-02-the-answer-not-followed",
    file: "src/components/onboarding/useSelfie.ts",
    old: "        advance(me);\n",
    new: "",
    run: [SELFIE_TEST],
    expect: [
      "a man can",
      "Continue finishes sign-up",
      "the button works again",
    ],
  },
  {
    id: "t48-finish-03-a-stale-match-kept",
    file: "src/components/onboarding/useSelfie.ts",
    old: "          void queryClient.invalidateQueries({ queryKey: queryKeys.me() });\n          void latest.refetch();\n",
    new: "",
    run: [SELFIE_TEST],
    expect: ["a match the server doesn't know of"],
  },
  {
    id: "t48-finish-04-asked-twice-at-once",
    file: "src/components/onboarding/SelfieStep.tsx",
    old: "      disabled={selfie.finishing}\n",
    new: "",
    run: [SELFIE_TEST],
    expect: ["can't be asked twice at once"],
  },
  {
    id: "t48-copy-01-the-last-named-not-the-first",
    file: "src/components/onboarding/selfieCopy.ts",
    old: "named.find(isMissing)",
    new: "named.findLast(isMissing)",
    run: [SELFIE_TEST],
    expect: ["names the first of"],
  },
  {
    id: "t48-copy-02-no-way-back",
    file: "src/components/onboarding/SelfieStep.tsx",
    old: "      {copy.place && (",
    new: "      {false && (",
    run: [SELFIE_TEST],
    expect: ["names the first of"],
  },
  {
    id: "t48-copy-03-any-name-trusted",
    file: "src/components/onboarding/selfieCopy.ts",
    old: "  MISSING.some((listed) => listed === name);",
    new: '  typeof name === "string";',
    run: [SELFIE_TEST],
    expect: ["a name it doesn't know"],
  },
  {
    id: "t48-copy-04-no-match-unsaid",
    file: "src/components/onboarding/selfieCopy.ts",
    old: '  if (error instanceof ApiError && error.code === "VERIFICATION_REQUIRED") {\n',
    new: "  if (false) {\n",
    run: [SELFIE_TEST],
    expect: ["a match the server doesn't know of"],
  },

  // --- T-4.12: the face photo, and the words that say what it is (D-391) ---
  {
    id: "t412-copy-01-the-selfie-compared-with-your-photos-again",
    file: "src/i18n/en.ts",
    old: '        "Needed before your profile goes live. We compare your selfie with your face photo.",',
    new: '        "Needed before your profile goes live. We compare your selfie with the photos on your profile.",',
    run: [SELFIE_TEST],
    expect: ["says the selfie is compared with the face photo"],
  },
  {
    id: "t412-copy-02-the-face-photo-called-a-verification-photo",
    file: "src/i18n/en.ts",
    old: '        title: "Your face photo",',
    new: '        title: "Your verification photo",',
    run: [CLAIMS_TEST],
    expect: ["says none of the claims anywhere but the two named keys"],
  },
  {
    id: "t412-badge-01-the-badge-says-matches-photos",
    file: "src/i18n/en.ts",
    old: '    selfieMatched: "Selfie matched",',
    new: '    selfieMatched: "Selfie matches photos",',
    run: ["src/components/ui/Avatar.test.tsx"],
    expect: ["the badge as 'Selfie matched'"],
  },
  {
    id: "t412-step-01-a-woman-let-on-without-a-face-photo",
    file: "src/components/onboarding/PhotosStep.tsx",
    old: "  const mayGo = optional || face.hasOne;",
    new: "  const mayGo = true;",
    run: [STEP_TEST],
    expect: ["a woman has no way on until her face photo is there"],
  },
  {
    id: "t412-step-02-the-face-photo-sent-as-public",
    file: "src/lib/queries/photos.ts",
    old: 'uploadPhoto(body, "verification", undefined, onProgress)',
    new: 'uploadPhoto(body, "public", 0, onProgress)',
    run: [HOOKS_TEST, STEP_TEST],
    expect: ["uploads it as kind verification with no place"],
  },
  {
    id: "t412-step-03-the-exit-back-to-reading-me",
    file: "src/lib/queries/photos.ts",
    old: '      return api.post("/v1/me/photos/done");',
    new: '      return api.get("/v1/me");',
    run: [HOOKS_TEST, STEP_TEST],
    expect: [
      "leaves the step by its own exit",
      "leaves by the step's own exit",
    ],
  },
  {
    id: "t412-slot-01-the-toggle-before-approval",
    file: "src/components/onboarding/FaceSlot.tsx",
    old: 'disabled={view.kind !== "approved" || slot.toggling}',
    new: "disabled={slot.toggling}",
    run: [STEP_TEST],
    expect: [
      "uploads it as kind verification with no place, shows it checking, then approved",
    ],
  },
  {
    id: "t412-slot-02-the-face-photo-changeable-after-the-match",
    file: "src/components/onboarding/FaceSlot.tsx",
    old: "{live && !locked && (",
    new: "{live && (",
    run: [STEP_TEST],
    expect: ["can't change once the selfie matched"],
  },
  // T-8.11 (D-470, D-530): the welcome toast says only what the server gave.
  {
    id: "t811-toast-01-shown-at-nothing",
    file: "src/components/onboarding/useSelfie.ts",
    old: "        if (me.balance > 0) {\n",
    new: "        if (me.balance >= 0) {\n",
    run: [SELFIE_TEST],
    expect: ["a number that had its welcome finishes with no toast"],
  },
  {
    id: "t811-toast-02-one-velas",
    file: "src/components/onboarding/useSelfie.ts",
    old: "              me.balance === 1\n",
    new: "              me.balance === 0\n",
    run: [SELFIE_TEST],
    expect: ["one Vela is one, in the singular"],
  },

  // --- T-6.6: search, and the nonce routes' CSP (D-540, D-541) ---
  {
    id: "t66-search-01-asks-for-every-letter",
    file: "src/components/search/useDebounced.ts",
    old: "const timer = setTimeout(() => setSettled(value), ms);",
    new: "setSettled(value);\n    const timer = setTimeout(() => {}, ms);",
    run: [SEARCH_TEST],
    expect: ["asks once typing pauses, not for each letter"],
  },
  {
    id: "t66-search-02-asks-what-the-api-refuses",
    file: "src/components/search/searchQuery.ts",
    old: '  if (q.length < SEARCH_TEXT_MIN) return { kind: "tooShort" };\n',
    new: "",
    run: [SEARCH_TEST],
    expect: ["says why, and asks nothing"],
  },
  {
    id: "t66-search-03-their-text-as-markup",
    file: "src/components/search/SearchResultRow.tsx",
    old: '      <span className="flex min-w-0 flex-1 flex-col">',
    new: '      <span dangerouslySetInnerHTML={{ __html: person.first_name }} />\n      <span className="flex min-w-0 flex-1 flex-col">',
    run: [SEARCH_TEST],
    expect: ["renders another person's text as text, never as markup"],
  },
  {
    id: "t66-search-04-a-badge-for-everyone",
    file: "src/components/search/SearchResultRow.tsx",
    old: "verified={person.shows_badge}",
    new: "verified={true}",
    run: [SEARCH_TEST],
    expect: ["shows the badge only where the API says it shows"],
  },
  {
    id: "t66-csp-01-inline-kept-beside-the-nonce",
    file: HEADERS,
    old: "`'nonce-${nonce}' 'strict-dynamic'`",
    new: "`'nonce-${nonce}' 'strict-dynamic' 'unsafe-inline'`",
    run: [CSP_TEST],
    expect: ["differs from the static one in script-src alone"],
  },
  {
    id: "t66-csp-02-a-route-left-to-the-static-policy",
    file: "src/proxy.ts",
    old: '    "/you/:path*",\n',
    new: "",
    run: [CSP_TEST],
    expect: [
      "has the proxy match exactly NONCE_ROUTES",
      "leaves /you to the proxy",
    ],
  },
  {
    id: "t66-csp-03-two-policies-on-a-nonce-route",
    file: HEADERS,
    old: '  return `/((?!(?:${NONCE_ROUTES.join("|")})(?:/|$)|@${USERNAME_IN_PATH}$).*)`;',
    new: '  return "/(.*)";',
    run: [CSP_TEST],
    expect: [
      "leaves /login to the proxy",
      "leaves /discover/search to the proxy",
    ],
  },
  {
    id: "t66-csp-04-a-page-built-ahead-without-its-nonce",
    file: "src/app/(app)/layout.tsx",
    old: 'export const dynamic = "force-dynamic";',
    new: 'export const dynamic = "auto";',
    run: [PROXY_TEST],
    expect: ["has (auth) and (app) force dynamic rendering"],
  },
  {
    id: "t66-csp-05-served-under-no-policy",
    file: HEADERS,
    old: '    throw new Error("The build has no nonce policy: CSP_WITH_NONCE is unset");',
    new: "    return template;",
    run: [CSP_TEST, PROXY_TEST],
    expect: [
      "never serves a nonce route under no policy",
      "refuses to serve a page when the build has no nonce policy",
    ],
  },
  // --- T-6.5: the deck. The price shown is the price sent (P-56) ---
  {
    id: "t65-01-super-sends-a-literal",
    file: DECK,
    old: 'void send(card, dir, dir === "super" ? (superPrice ?? 0) : 0);',
    new: 'void send(card, dir, dir === "super" ? 5 : 0);',
    run: [DECK_TEST],
    expect: [SHOWN, HER_DECK],
  },
  {
    id: "t65-02-super-badge-a-literal",
    file: "src/components/discover/ActionRow.tsx",
    old: "<PriceTag credits={superPrice} />",
    new: "<PriceTag credits={5} />",
    run: [DECK_TEST],
    expect: [SHOWN, "says the new price and asks /prices again"],
  },
  {
    id: "t65-03-a-woman-shown-prices",
    file: DECK,
    old: "    if (!isMan) return null;\n",
    new: "",
    run: [DECK_TEST],
    expect: [HER_DECK, HER_THREAD],
  },
  {
    id: "t65-04-thread-sends-a-literal",
    file: "src/components/discover/MatchSheet.tsx",
    old: "shown_price: openPrice ?? 0,",
    new: "shown_price: 5,",
    run: [DECK_TEST],
    expect: [HIS_THREAD, HER_THREAD],
  },
  {
    id: "t65-05-price-changed-not-asked-again",
    file: "src/lib/queries/QueryProvider.tsx",
    old: "          void client.invalidateQueries({ queryKey: queryKeys.prices() });\n",
    new: "",
    run: [PROVIDER_TEST, DECK_TEST],
    expect: [
      "asks for /prices again when a mutation is refused with PRICE_CHANGED",
      "says the new price and asks /prices again",
    ],
  },
  // --- The optimistic swipe ---
  {
    id: "t65-06-never-put-back",
    file: DECK,
    old: "        putBack(card.id);\n",
    new: "",
    run: [DECK_TEST],
    expect: [
      "puts the card back with a toast after a network failure",
      "puts the card back with a toast after a 500",
      "opens the store when he is out of Velas",
      "says the new price and asks /prices again",
      "at the cap",
    ],
  },
  {
    id: "t65-07-put-back-when-gone-anyway",
    file: DECK,
    old: '  "ALREADY_EXISTS",\n  "NOT_FOUND",\n]);',
    new: "]);",
    run: [DECK_TEST],
    expect: ["leaves the card gone after ALREADY_EXISTS", "after NOT_FOUND"],
  },
  {
    id: "t65-08-the-cap-not-held",
    file: DECK,
    old: 'if (isMan && dir !== "super" && swipesLeft === 0) {',
    new: "if (false) {",
    run: [DECK_TEST],
    expect: ["at the cap"],
  },
  // --- What is drawn and asked for ---
  {
    id: "t65-09-every-card-drawn",
    file: "src/components/discover/Deck.tsx",
    old: "export const RENDERED = 3;",
    new: "export const RENDERED = 30;",
    run: [DECK_TEST],
    expect: ["draws three cards at most"],
  },
  {
    id: "t65-10-next-page-asked-early",
    file: DECK,
    old: "export const PREFETCH_AT = 5;",
    new: "export const PREFETCH_AT = 6;",
    run: [DECK_TEST],
    expect: ["asks for the next page when 5 cards are left"],
  },
  {
    id: "t65-11-next-page-never-asked",
    file: DECK,
    old: "if (cards.length <= PREFETCH_AT && hasNextPage && !isFetchingNextPage) {",
    new: "if (cards.length < 0 && hasNextPage && !isFetchingNextPage) {",
    run: [DECK_TEST],
    expect: ["asks for the next page when 5 cards are left"],
  },
  {
    id: "t65-12-super-like-not-spending",
    file: "src/lib/queries/discover.ts",
    old: '      api.post("/v1/swipes", { body: variables }),\n    meta: { touchesWallet: true },\n',
    new: '      api.post("/v1/swipes", { body: variables }),\n',
    run: [DECK_TEST],
    expect: ["marks a Super Like as spending Velas"],
  },
  {
    id: "t65-13-thread-not-spending",
    file: "src/lib/queries/discover.ts",
    old: '      api.post("/v1/threads", { body: variables }),\n    meta: { touchesWallet: true },\n',
    new: '      api.post("/v1/threads", { body: variables }),\n',
    run: [DECK_TEST],
    expect: [HIS_THREAD],
  },
  // --- The badge (D-393) and the keys ---
  {
    id: "t65-14-tick-on-a-silhouette",
    file: "src/components/discover/SwipeCard.tsx",
    old: "const badge = card.shows_badge && photo !== null;",
    new: "const badge = card.shows_badge;",
    run: [DECK_TEST],
    expect: ["with no photo"],
  },
  {
    id: "t65-15-tick-unearned",
    file: "src/components/discover/SwipeCard.tsx",
    old: "const badge = card.shows_badge && photo !== null;",
    new: "const badge = photo !== null;",
    run: [DECK_TEST],
    expect: ["no tick"],
  },
  {
    id: "t65-16-keys-taken-from-a-field",
    file: DECK,
    old: "      if (typing(event.target)) return;\n",
    new: "",
    run: [DECK_TEST],
    expect: ["leaves the keys alone"],
  },
  {
    id: "t65-17-profile-left-to-the-static-csp",
    file: HEADERS,
    old: '  "people",\n',
    new: "",
    run: [CSP_TEST],
    expect: ["has the proxy match exactly NONCE_ROUTES", "leaves /people/"],
  },
  // --- T-6.7: Liked you (D-542, D-543) ---
  {
    id: "t67-likes-01-a-css-blur",
    file: "src/components/likes/LikeTile.tsx",
    old: '              alt={t("likes.someone")}\n              className="size-full object-cover"',
    new: '              alt={t("likes.someone")}\n              className="size-full object-cover blur-xl"',
    run: [LIKES_TEST],
    expect: ["shows a man the server's blur, never a CSS one"],
  },
  {
    id: "t67-likes-02-a-price-written-in",
    file: "src/components/likes/LikedYouScreen.tsx",
    old: "const price = man ? prices.data?.liked_you_reveal : undefined;",
    new: "const price = man ? 1 : undefined;",
    run: [LIKES_TEST],
    expect: ["the price from /prices"],
  },
  {
    id: "t67-likes-03-a-woman-asked-for-prices",
    file: "src/components/likes/LikedYouScreen.tsx",
    old: "const prices = usePrices({ enabled: man });",
    new: "const prices = usePrices();",
    run: [LIKES_TEST],
    expect: ["shows a woman everyone, with no reveal and no prices asked"],
  },
  {
    id: "t67-likes-04-a-price-never-shown",
    file: "src/components/likes/LikedYouScreen.tsx",
    old: "{ handle, shownPrice: price ?? 0 }",
    new: "{ handle, shownPrice: 0 }",
    run: [LIKES_TEST],
    expect: ["reveals one, and the tile shows who it was"],
  },
  // --- T-6.8: the profile and /@username (D-544) ---
  {
    id: "t68-profile-01-a-badge-for-everyone",
    file: "src/components/profile/ProfileScreen.tsx",
    old: '{person.shows_badge && (\n              <span className="bg-accent text-on-accent',
    new: '{true && (\n              <span className="bg-accent text-on-accent',
    run: [PROFILE_TEST],
    expect: ["shows no badge or note where D-393's rule doesn't hold"],
  },
  {
    id: "t68-share-01-onboarding-redirected",
    file: "src/components/share/SignedInProfileRedirect.tsx",
    old: 'gate.kind === "ready" && gate.me.onboarding_step === "done"',
    new: 'gate.kind === "ready"',
    run: [REDIRECT_TEST],
    expect: ["asks nothing for someone still onboarding"],
  },
  {
    id: "t68-share-02-indexed",
    file: "src/app/(share)/layout.tsx",
    old: "robots: { index: false, follow: false },",
    new: "robots: { index: true, follow: true },",
    run: [SHARE_LAYOUT_TEST],
    expect: ["is never indexed, in any environment"],
  },
  {
    id: "t68-share-03-any-at-path",
    file: "src/lib/security-headers.ts",
    old: "export const AT_USERNAME = `/@:username(${USERNAME_IN_PATH})`;",
    new: 'export const AT_USERNAME = "/@:username";',
    run: [ROUTES_TEST, CSP_TEST],
    expect: ["serves /@username through the internal /share route"],
  },
  {
    id: "t68-share-04-the-page-under-the-static-policy",
    file: "src/proxy.ts",
    old: '    "/share/:path*",\n',
    new: "",
    run: [CSP_TEST],
    expect: ["leaves /share/priya to the proxy"],
  },
  // --- T-6.9: the filters. In the URL, one place writes them; the server applies them (D-660) ---
  {
    id: "t69-01-online-never-sent",
    file: "src/lib/queries/discover.ts",
    old: "          online: filters.online || undefined,\n",
    new: "",
    run: [DECK_TEST],
    expect: [ASKS_ALL, "a change of Online now alone is a new scroll"],
  },
  {
    id: "t69-02-online-left-out-of-the-key",
    file: "src/lib/queries/keys.ts",
    old: "        online: filters.online,\n",
    new: "",
    run: [DECK_TEST],
    expect: ["a change of Online now alone is a new scroll"],
  },
  {
    id: "t69-03-online-never-read",
    file: FILTER_PARAMS,
    old: '    online: params.get("online") === "true",',
    new: "    online: false,",
    run: [DECK_TEST],
    expect: [ASKS_ALL, BADGE_COUNTS, "the empty deck's Clear filters"],
  },
  {
    id: "t69-04-toggles-not-counted",
    file: FILTER_PARAMS,
    old: "    (filters.online ? 1 : 0)",
    new: "    0",
    run: [DECK_TEST, FILTERS_TEST],
    expect: [BADGE_COUNTS, "counts one filter as one", DRAFT],
  },
  {
    id: "t69-05-show-drops-verified",
    file: FILTER_PARAMS,
    old: '  if (filters.verified) params.set("verified", "true");\n',
    new: "",
    run: [DECK_TEST],
    expect: [SHOW_WRITES],
  },
  {
    id: "t69-06-empty-clear-keeps-online",
    file: DECK,
    old: "onClear={() => applyFilters(NO_FILTERS)}",
    new: "onClear={() => applyFilters({ ...NO_FILTERS, online: filters.online })}",
    run: [DECK_TEST],
    expect: ["the empty deck's Clear filters"],
  },
  {
    id: "t69-07-draft-applied-live",
    file: FILTERS_SHEET,
    old: "onChange={(online) => setDraft((now) => ({ ...now, online }))}",
    new: "onChange={(online) => onApply({ ...draft, online })}",
    run: [DECK_TEST, FILTERS_TEST],
    expect: [DRAFT, "closing the sheet writes nothing", SHOW_WRITES],
  },
  {
    id: "t69-08-sheet-starts-empty",
    file: FILTERS_SHEET,
    old: "useState<DiscoverFilters>(applied);",
    new: "useState<DiscoverFilters>(NO_FILTERS);",
    run: [DECK_TEST, FILTERS_TEST],
    expect: ["starts from the filters applied", SHOW_WRITES],
  },
  {
    id: "t69-09-clear-keeps-the-draft",
    file: FILTERS_SHEET,
    old: "onClick={() => setDraft(NO_FILTERS)}",
    new: "onClick={() => setDraft(applied)}",
    run: [DECK_TEST, FILTERS_TEST],
    expect: ["Clear empties the draft", "when the sheet's Clear is shown"],
  },
  {
    id: "t69-10-sheet-badge-not-drawn",
    file: "src/components/ui/Sheet.tsx",
    old: "            {badge}\n",
    new: "",
    run: [SHEET_TEST, FILTERS_TEST],
    expect: [
      "draws a badge beside its title",
      "starts from the filters applied",
      "counts one filter as one",
    ],
  },
  {
    id: "t69-11-the-chip-says-verified",
    file: "src/i18n/en.ts",
    old: '      selfie: "Selfie matched",',
    new: '      selfie: "Verified only",',
    run: [CLAIMS_TEST, FILTERS_TEST],
    expect: [
      "says none of the claims anywhere but the two named keys",
      "says what the toggles filter on",
    ],
  },
  // --- T-7.10: the chats list. Her list says nothing about time (P-460) ---
  {
    id: "t710-01-her-countdown",
    file: "src/components/chats/ChatRow.tsx",
    old: "man && !knotted && row.expires_at !== null",
    new: "!knotted && row.expires_at !== null",
    run: [CHATS_TEST],
    expect: [HER_ROWS],
  },
  {
    id: "t710-02-her-clear-expired",
    file: CHATS,
    old: '{man && tier === "threads" && !selecting',
    new: '{tier === "threads" && !selecting',
    run: [CHATS_TEST],
    expect: ["offers her no Clear expired and no footer"],
  },
  {
    id: "t710-03-her-footer",
    file: CHATS,
    old: '      {man && (\n        <p className="text-small text-mute px-',
    new: '      {true && (\n        <p className="text-small text-mute px-',
    run: [CHATS_TEST],
    expect: ["offers her no Clear expired and no footer"],
  },
  {
    id: "t710-04-a-blacklist-gate",
    file: CHATS,
    old: 'const man = useMe().data?.gender === "male";',
    new: 'const man = useMe().data?.gender !== "female";',
    run: [CHATS_TEST],
    expect: ["shows nobody a countdown while it isn't yet known"],
  },
  {
    id: "t710-05-a-ticker-per-reader",
    file: TICKER,
    old: "  if (timer === undefined) {",
    new: "  if (true) {",
    run: [TICKER_TEST],
    expect: [ONE_TICKER],
  },
  {
    id: "t710-06-the-ticker-never-stops",
    file: TICKER,
    old: "      clearInterval(timer);\n",
    new: "",
    run: [TICKER_TEST],
    expect: [ONE_TICKER],
  },
  {
    id: "t710-07-urgent-at-ten",
    file: COUNTDOWN,
    old: "leftMs < URGENT_MS",
    new: "leftMs <= URGENT_MS",
    run: [COUNTDOWN_TEST],
    expect: ["fills --accent under ten minutes, and not at ten"],
  },
  {
    id: "t710-08-extended-at-the-hour",
    file: COUNTDOWN,
    old: "  if (leftMs > HOUR_MS) {",
    new: "  if (leftMs >= HOUR_MS) {",
    run: [COUNTDOWN_TEST],
    expect: ["reads a full hour as the hour, not as Extended"],
  },
  {
    id: "t710-09-ran-out-by-status",
    file: CHATS,
    old: "      Date.parse(row.expires_at) <= now,",
    new: '      row.status === "expired",',
    run: [CHATS_TEST],
    expect: ["counts Clear expired by the clock"],
  },
  {
    id: "t710-10-undo-never-restores",
    file: CHATS,
    old: "              restore.mutate(row.id, {",
    new: "              clearOne.mutate(row.id, {",
    run: [CHATS_TEST],
    expect: [TAKEN_OUT],
  },
  {
    id: "t710-11-undo-held-too-long",
    file: CHATS,
    old: "const UNDO_MS = 5000;",
    new: "const UNDO_MS = 8000;",
    run: [CHATS_TEST],
    expect: ["offers Undo for exactly 5 s"],
  },
  {
    id: "t710-12-refused-row-left-out",
    file: THREADS_HOOKS,
    old: "      for (const [key, data] of before ?? []) client.setQueryData(key, data);\n",
    new: "",
    run: [CHATS_TEST],
    expect: ["puts the row back and says so when the clear is refused"],
  },
  {
    id: "t710-13-row-kept-until-answered",
    file: THREADS_HOOKS,
    old: "    onMutate: (id) => takeOut(client, id),\n",
    new: "",
    run: [CHATS_TEST],
    expect: [TAKEN_OUT],
  },
  {
    id: "t710-14-search-untrimmed",
    file: CHATS,
    old: "setQ(text.trim().slice(0, THREADS_Q_MAX))",
    new: "setQ(text.slice(0, THREADS_Q_MAX))",
    run: [CHATS_TEST],
    expect: ["asks by name, trimmed, and never sends an empty search"],
  },
  {
    id: "t710-15-empty-search-sent",
    file: THREADS_HOOKS,
    old: '          q: q === "" ? undefined : q,',
    new: "          q,",
    run: [THREADS_HOOKS_TEST],
    expect: ["q only when it says something"],
  },
  {
    id: "t710-16-search-uncapped",
    file: CHATS,
    old: "setQ(text.trim().slice(0, THREADS_Q_MAX))",
    new: "setQ(text.trim())",
    run: [CHATS_TEST],
    expect: ["never sends more than the API takes: 50 characters"],
  },
  {
    id: "t710-17-select-past-the-cap",
    file: CHATS,
    old: "const atCap = selected.size >= CLEAR_MAX;",
    new: "const atCap = selected.size > CLEAR_MAX;",
    run: [CHATS_TEST],
    expect: ["takes at most 100 at a time"],
  },
  {
    id: "t710-18-a-smaller-page",
    file: THREADS_HOOKS,
    old: "export const THREADS_PAGE = 50;",
    new: "export const THREADS_PAGE = 20;",
    run: [CHATS_TEST, THREADS_HOOKS_TEST],
    expect: [COUNTS, "50 a page"],
  },
  {
    id: "t710-19-a-knots-filter-on-threads",
    file: CHATS,
    old: 'const listFilter = tier === "knots" ? filter : "all";',
    new: "const listFilter = filter;",
    run: [CHATS_TEST],
    expect: ["a filter chosen there never reaches Threads"],
  },
  {
    id: "t710-20-never-more",
    file: CHATS,
    old: "more: first.next_cursor !== null",
    new: "more: false",
    run: [CHATS_TEST],
    expect: [COUNTS],
  },
  // --- T-8.7: the store and its checkout ---
  {
    id: "t87-01-a-woman-sees-the-store",
    file: STORE_SHEET,
    old: "  if (!isMan) return null;\n",
    new: "",
    run: [STORE_TEST],
    expect: ["opened anyway, nothing shows"],
  },
  {
    id: "t87-02-a-womans-browser-asks-for-packs",
    file: STORE_SHEET,
    old: "usePacks({ enabled: open && isMan })",
    new: "usePacks({ enabled: open })",
    run: [STORE_TEST],
    expect: ["opened anyway, nothing shows"],
  },
  {
    id: "t87-03-best-value-is-the-first-pack",
    file: STORE_MATH,
    old: "return tied || best === null ? null : best.id;",
    new: "return packs[0]?.id ?? null;",
    run: [STORE_MATH_TEST, PACKS_TEST],
    expect: [
      "is the ₹10,000 pack today",
      '"Best value" is on the cheapest Vela alone',
    ],
  },
  {
    id: "t87-04-best-value-on-a-tie",
    file: STORE_MATH,
    old: "tied = true;",
    new: "tied = false;",
    run: [STORE_MATH_TEST],
    expect: ["is none when two packs tie"],
  },
  {
    id: "t87-05-try-again-makes-a-second-order",
    file: STORE_SHEET,
    old: "onRetry={() => openWindow(paying)}",
    new: "onRetry={() => buy(paying.pack)}",
    run: [STORE_TEST],
    expect: [
      "Try again reopens the same order, never a second",
      "Try again opens the same order again",
    ],
  },
  {
    id: "t87-06-no-sixty-second-cap",
    file: STORE_QUERIES,
    old: "export const POLL_FOR_MS = 60_000;",
    new: "export const POLL_FOR_MS = 600_000;",
    run: [STORE_QUERIES_TEST, STORE_TEST],
    expect: ["polls every 1.5 s, for 60 s at most", "stops at 60 s"],
  },
  {
    id: "t87-07-polls-every-second",
    file: STORE_QUERIES,
    old: "export const POLL_EVERY_MS = 1_500;",
    new: "export const POLL_EVERY_MS = 1_000;",
    run: [STORE_QUERIES_TEST, STORE_TEST],
    expect: ["polls every 1.5 s, for 60 s at most", "asks every 1.5 s"],
  },
  {
    id: "t87-08-the-shown-price-unchecked",
    file: STORE_SHEET,
    old: "if (order.amount_paise !== pack.price_paise) {",
    new: "if (order.amount_paise < 0) {",
    run: [STORE_TEST],
    expect: ["a price other than the one shown"],
  },
  {
    id: "t87-09-razorpay-on-static-pages",
    file: HEADERS,
    old: "const razorpay = nonce !== undefined && paysByRazorpay(env);",
    new: "const razorpay = paysByRazorpay(env);",
    run: [CSP_TEST],
    expect: ["never on the static pages"],
  },
  {
    id: "t87-10-local-pays-by-razorpay",
    file: CHECKOUT_PATH,
    old: '["local", "standin"],',
    new: '["local", "razorpay"],',
    run: [CHECKOUT_PATH_TEST, CSP_TEST],
    expect: ["local pays by standin", "never on a stand-in build"],
  },
  {
    id: "t87-11-the-stand-in-on-a-razorpay-build",
    file: CHECKOUT_PATH,
    old: 'if (path === "razorpay") return keyId === FAKE_KEY_ID ? null : "razorpay";',
    new: 'if (path === "razorpay") return keyId === FAKE_KEY_ID ? "standin" : "razorpay";',
    run: [CHECKOUT_PATH_TEST, STORE_TEST],
    expect: [
      "a Razorpay build never opens the stand-in, even for the fake's key",
      "a Razorpay build never opens the stand-in, even for the fake's order",
    ],
  },
  {
    id: "t87-12-gst-in-the-store",
    file: "src/i18n/en.ts",
    old: 'final: "Purchases are final. A payment that goes wrong is ours to fix.",',
    new: 'final: "Purchases are final. Prices include GST.",',
    run: [STORE_TEST],
    expect: ['never "GST"'],
  },
  {
    id: "t87-13-most-popular-on-day-one",
    file: "src/i18n/en.ts",
    old: 'bestValue: "Best value",',
    new: 'bestValue: "Most popular",',
    run: [STORE_TEST, PACKS_TEST],
    expect: [
      'never "Most popular"',
      '"Best value" is on the cheapest Vela alone',
    ],
  },
  {
    id: "t87-14-a-claim-refusal-unsaid",
    file: "src/components/wallet/ClaimForm.tsx",
    old: 'case "ALREADY_EXISTS":\n      return "wallet.store.claim.already";',
    new: 'case "ALREADY_EXISTS":\n      return "wallet.store.claim.failed";',
    run: ["src/components/wallet/ClaimForm.test.tsx"],
    expect: ["refused with ALREADY_EXISTS"],
  },
  {
    id: "t87-15-the-order-not-touches-wallet",
    file: STORE_QUERIES,
    old: "    meta: { touchesWallet: true },\n    mutationFn: ({ packId, key }",
    new: "    mutationFn: ({ packId, key }",
    run: [STORE_QUERIES_TEST],
    expect: ["is marked touchesWallet"],
  },
  {
    id: "t87-16-paid-refreshes-nothing",
    file: STORE_QUERIES,
    old: "    void queryClient.invalidateQueries({ queryKey: queryKeys.wallet() });\n    void queryClient.invalidateQueries({ queryKey: queryKeys.packs() });\n  }, [paid, queryClient]);",
    new: "  }, [paid, queryClient]);",
    run: [STORE_QUERIES_TEST],
    expect: ["the balance and the packs asked again"],
  },
  {
    id: "t87-17-a-dismissal-after-paying",
    file: "src/lib/razorpay.ts",
    old: "if (!paid) onDismiss();",
    new: "onDismiss();",
    run: ["src/lib/razorpay.test.ts"],
    expect: ["closing the window afterwards isn't a dismissal"],
  },
  // --- T-7.11: the conversation ---
  {
    id: "t711-01-her-countdown",
    file: SCREEN,
    old: '    man && view && view.status !== "knotted" && view.expires_at\n',
    new: '    view && view.status !== "knotted" && view.expires_at\n',
    run: [SCREEN_TEST],
    expect: [
      "draws no countdown, no bar, no Extend and no price",
      "shows her no expired state on an expired Thread",
    ],
  },
  {
    id: "t711-02-his-send-at-no-price",
    file: SCREEN,
    old: "shown_price: man ? (view?.send_price ?? 0) : 0,",
    new: "shown_price: 0,",
    run: [SCREEN_TEST],
    expect: [
      "shows his message's price before he sends it, and sends exactly it",
    ],
  },
  {
    id: "t711-03-an-unlock-at-no-price",
    file: "src/components/conversation/VoiceNote.tsx",
    old: "        shown_price: unlockPrice,\n",
    new: "        shown_price: 0,\n",
    run: [SCREEN_TEST],
    expect: ["unlocks it at exactly that price"],
  },
  {
    id: "t711-04-time-at-no-price",
    file: SCREEN,
    old: "        shown_price: price,\n        key,\n",
    new: "        shown_price: 0,\n        key,\n",
    run: [SCREEN_TEST],
    expect: [
      "Extend at /prices' price, sending exactly it",
      "re-opens at the price shown",
    ],
  },
  {
    id: "t711-05-his-mic",
    file: SCREEN,
    old: "canRecord={woman}",
    new: "canRecord",
    run: [SCREEN_TEST],
    expect: ["shows the hour left, the bar, and Extend"],
  },
  {
    id: "t711-06-enter-while-composing",
    file: "src/components/conversation/Composer.tsx",
    old: "    if (event.nativeEvent.isComposing) return;\n",
    new: "",
    run: [COMPOSER_TEST],
    expect: ["never on Shift+Enter or while an input method composes"],
  },
  {
    id: "t711-07-a-refusal-loses-the-text",
    file: SCREEN,
    old: "        drop(client_msg_id);\n        restore(body);\n",
    new: "        drop(client_msg_id);\n",
    run: [SCREEN_TEST],
    expect: [
      "explains a message refused for abuse",
      "says what RATE_LIMITED means and keeps the text",
    ],
  },
  {
    id: "t711-08-a-retry-with-a-new-id",
    file: SCREEN,
    old: "void sendText(item.body, item.client_msg_id);",
    new: "void sendText(item.body);",
    run: [SCREEN_TEST],
    expect: [
      "keeps a failed message with Retry, which sends the same client id",
    ],
  },
  {
    id: "t711-09-her-knot-sheet-names-the-hour",
    file: "src/components/conversation/KnotTiedSheet.tsx",
    old: 't(man ? "conversation.tied.bodyHis" : "conversation.tied.bodyHers")',
    new: 't("conversation.tied.bodyHis")',
    run: [SCREEN_TEST],
    expect: ["celebrates the second tap for a female"],
  },
  {
    id: "t711-10-the-microphone-to-anyone",
    file: HEADERS,
    old: '"camera=(self), microphone=(self), geolocation=(self), browsing-topics=()",',
    new: '"camera=(self), microphone=*, geolocation=(self), browsing-topics=()",',
    run: [CSP_TEST],
    expect: ["and the microphone (T-7.11) to this site alone"],
  },
  {
    id: "t711-11-no-voice-links",
    file: HEADERS,
    old: "    media: ` blob: ${storage.privateBucket}`,\n",
    new: "    media: ` blob:`,\n",
    run: [CSP_TEST],
    expect: [
      "adds exactly the local S3's photo sources",
      "adds what React's dev tooling needs",
    ],
  },
  {
    id: "t711-12-no-cap",
    file: "src/lib/voice-recorder.ts",
    old: "  }, VOICE_MAX_MS);\n",
    new: "  }, VOICE_MAX_MS * 2);\n",
    run: ["src/lib/voice-recorder.test.ts"],
    expect: ["stops itself at a minute"],
  },
  {
    id: "t711-13-untie-at-once",
    file: "src/components/conversation/ConversationMenu.tsx",
    old: '              onClick={() => setOpen("confirm")}\n',
    new: "              onClick={() => void onUntie()}\n",
    run: [SCREEN_TEST],
    expect: ["unties a Knot only once asked twice"],
  },
  {
    id: "t711-14-under-a-second-kept",
    file: "src/components/conversation/MicButton.tsx",
    old: "if (made.durationMs < VOICE_MIN_MS) {",
    new: "if (made.durationMs < 0) {",
    run: [MIC_TEST],
    expect: ["throws away anything under a second"],
  },
  {
    id: "t711-15-the-recorder-page-everywhere",
    file: "src/app/dev/voice/page.tsx",
    old: '  if (process.env.NODE_ENV !== "development") notFound();\n',
    new: "",
    run: ["src/app/dev/voice/page.test.tsx"],
    expect: ["is not found when NODE_ENV is"],
  },
  {
    id: "t711-16-sent-before-heard",
    file: "src/components/conversation/MicButton.tsx",
    old: '      setRecording(made);\n      setPhase("preview");\n',
    new: '      onSend(made);\n      setPhase("idle");\n',
    run: [MIC_TEST],
    expect: ["plays it back before anything is sent"],
  },
  // --- T-9.4: notifications and the service worker ---------------------------
  {
    id: "t94-web-01-her-hour-switch",
    file: "src/components/notifications/NotificationSettings.tsx",
    old: "    ...(man\n",
    new: "    ...(true\n",
    run: ["src/components/notifications/NotificationSettings.test.tsx"],
    expect: ["never shows her a switch about an hour running out"],
  },
  {
    id: "t94-web-02-asked-every-match",
    file: "src/components/notifications/PushAsk.tsx",
    old: '    if (typeof window === "undefined" || push.askedBefore()) return false;\n',
    new: '    if (typeof window === "undefined") return false;\n',
    run: ["src/components/notifications/PushAsk.test.tsx"],
    expect: ["asks once per browser"],
  },
  {
    id: "t94-web-03-a-key-asked-for-nothing",
    file: "src/components/notifications/PushAsk.tsx",
    old: "usePushKey({ enabled: shown })",
    new: "usePushKey()",
    run: ["src/components/notifications/PushAsk.test.tsx"],
    expect: ["asks nothing once the person has decided, and requests nothing"],
  },
  {
    id: "t94-web-04-a-click-leaves-the-site",
    file: "src/lib/push-worker.ts",
    old: "  const target = url.origin === self.location.origin ? url.href : new URL(TABLES.fallback, self.location.origin).href;\n",
    new: "  const target = url.href;\n",
    run: ["src/lib/push-worker.test.ts"],
    expect: ["never leaves the site"],
  },
  {
    id: "t94-web-05-ids-unencoded",
    file: "src/lib/push-worker.ts",
    old: "    return encodeURIComponent(value);\n",
    new: "    return value;\n",
    run: ["src/lib/push-worker.test.ts"],
    expect: ["keeps ids inside their path segment"],
  },
  {
    id: "t94-web-06-the-worker-drops-names",
    file: "src/lib/push-worker.ts",
    old: 'const body = name ? words.named.split("{name}").join(name) : words.plain;',
    new: "const body = words.plain;",
    run: ["src/lib/push-worker.test.ts"],
    expect: ["shows match"],
  },
  {
    id: "t94-web-07-no-worker-src",
    file: "src/lib/security-headers.ts",
    old: "    \"worker-src 'self'\",\n",
    new: "",
    run: ["src/lib/security-headers.test.ts"],
    expect: ["is exactly what a build without photo storage needs"],
  },
  {
    id: "t94-web-09-a-gift-not-to-its-sender",
    file: "src/lib/notification-view.ts",
    old: '  gift: "/people/{user_id}",\n',
    new: '  gift: "/you",\n',
    run: [
      "src/lib/push-worker.test.ts",
      "src/components/notifications/NotificationsScreen.test.tsx",
    ],
    expect: [
      "opens the sender's profile for a gift",
      "leads a gift to its sender's profile",
    ],
  },
  {
    id: "t94-web-08-the-list-unnonced",
    file: "src/lib/security-headers.ts",
    old: '  // The in-app notifications list (T-9.4).\n  "notifications",\n',
    new: "",
    run: ["src/lib/security-headers.test.ts"],
    expect: ["has the proxy match exactly NONCE_ROUTES"],
  },
  {
    id: "t712-web-01-her-hour-heard",
    file: REALTIME,
    old: '      if (gender !== "male") return;\n',
    new: "",
    run: [REALTIME_TEST],
    expect: [
      "reaching her changes nothing",
      "reaching someone whose gender isn't known yet",
    ],
  },
  {
    id: "t712-web-02-a-message-twice",
    file: REALTIME,
    old: "      if (known) return data;\n",
    new: "",
    run: [REALTIME_TEST],
    expect: ["once, and asks the lists again"],
  },
  {
    id: "t712-web-03-read-past-the-one-read",
    file: REALTIME,
    old: "            Date.parse(item.created_at) <= until\n",
    new: "            true\n",
    run: [REALTIME_TEST],
    expect: ["marks mine read up to the one they read"],
  },
  {
    id: "t712-web-04-dots-forever",
    file: REALTIME,
    old: "  if (on) {\n    typingTimers.set(",
    new: "  if (false) {\n    typingTimers.set(",
    run: [REALTIME_TEST],
    expect: ["lets them go 6 s after the last"],
  },
  {
    id: "t712-web-05-revoked-retried",
    file: WS,
    old: "const FINAL: ReadonlySet<number> = new Set([CLOSE.revoked, CLOSE.forbidden]);",
    new: "const FINAL: ReadonlySet<number> = new Set<number>([]);",
    run: [WS_TEST],
    expect: [
      "never reconnects after revoked sessions",
      "never reconnects after another origin",
    ],
  },
  {
    id: "t712-web-06-no-backoff",
    file: WS,
    old: "  return ceiling / 2 + (random * ceiling) / 2;",
    new: "  return 0 * ceiling * random;",
    run: [WS_TEST],
    expect: ["waits between half of each ceiling", "keeps backing off"],
  },
  {
    id: "t712-web-07-the-count-never-resets",
    file: WS,
    old: "    this.steadyTimer = setTimeout(() => {\n      this.attempt = 0;\n",
    new: "    this.steadyTimer = setTimeout(() => {\n",
    run: [WS_TEST],
    expect: ["starts the count again"],
  },
  {
    id: "t712-web-08-a-silent-socket-kept",
    file: WS,
    old: "      // Silent: give it up for a new one.\n      this.drop();\n      this.retry();\n",
    new: "      // Silent: give it up for a new one.\n",
    run: [WS_TEST],
    expect: ["gives the socket up when no pong comes"],
  },
  {
    id: "t712-web-09-never-paused",
    file: WS,
    old: "        this.paused = true;\n        this.drop();\n",
    new: "",
    run: [WS_TEST],
    expect: ["closes after 5 minutes hidden"],
  },
  {
    id: "t712-web-10-asked-again-on-first-connect",
    file: WS,
    old: "    if (again) this.options.onReconnect();",
    new: "    this.options.onReconnect();",
    run: [WS_TEST],
    expect: ["asks again only after a reconnect"],
  },
  {
    id: "t712-web-11-typing-unthrottled",
    file: WS,
    old: "    if (last !== undefined && now - last < TYPING_EVERY_MS) return;\n",
    new: "",
    run: [WS_TEST],
    expect: ["says typing at most once"],
  },
  {
    id: "t712-web-12-socket-on-static-pages",
    file: CSP712,
    old: "  const socket = nonce !== undefined ? socketOrigin(env) : null;",
    new: "  const socket = socketOrigin(env);",
    run: [CSP_TEST],
    expect: ["never on the static pages, APP_ENV=staging"],
  },
  {
    id: "t712-web-13-no-socket-allowed",
    file: CSP712,
    old: '${socket ? ` ${socket}` : ""}',
    new: "",
    run: [CSP_TEST],
    expect: ["adds wss:// for an https:// API"],
  },
  {
    id: "t712-web-14-gift-by-gender",
    file: SCREEN712,
    old: "              view.can_gift\n",
    new: '              me?.gender === "male"\n',
    run: [SCREEN_TEST],
    expect: ["follows can_gift for whoever the Thread says"],
  },
  {
    id: "t712-web-15-kudos-whatever-its-state",
    file: SCREEN712,
    old: '        {view.kudos === "can_give" && !deleted && (',
    new: "        {!deleted && (",
    run: [SCREEN_TEST],
    expect: ["is shown for too_early"],
  },
  {
    id: "t712-web-16-knot-sheet-on-opening",
    file: SCREEN712,
    old: "    if (knotSeen.current === undefined) {\n      knotSeen.current = knotAt;\n      return;\n    }\n",
    new: "    if (knotSeen.current === undefined) knotSeen.current = null;\n",
    run: [SCREEN_TEST],
    expect: ["never shows 'Knot tied' for a Knot that was already one"],
  },
  {
    id: "t712-web-17-knot-sheet-twice",
    file: SCREEN712,
    old: "        knotSeen.current = result.knotted_at;\n",
    new: "",
    run: [SCREEN_TEST],
    expect: ["opens once for my own tap"],
  },
  {
    id: "t712-web-18-knot-sheet-for-the-tapper-only",
    file: SCREEN712,
    old: "    if (knotAt !== null && knotAt !== knotSeen.current) setTiedOpen(true);\n",
    new: "",
    run: [SCREEN_TEST],
    expect: ["whose Thread became a Knot while it was open"],
  },
  {
    id: "t712-web-19-report-without-its-thread",
    file: REPORT_SHEET712,
    old: "              ...(threadId ? { thread_id: threadId } : {}),\n",
    new: "",
    run: [SCREEN_TEST],
    expect: ["reports with this Thread as the evidence"],
  },
  {
    id: "t712-web-20-the-chat-kept-after-a-block",
    file: SCREEN712,
    old: '    router.replace("/chats");\n',
    new: "",
    run: [SCREEN_TEST],
    expect: ["blocks silently and leaves the chat"],
  },
  {
    id: "t712-web-21-typing-for-blanks",
    file: COMPOSER712,
    old: '                if (event.target.value.trim() !== "") onTyping?.();',
    new: "                onTyping?.();",
    run: [SCREEN_TEST],
    expect: ["never for blanks"],
  },
  {
    id: "t712-web-22-ws-allowed-outside-lib",
    file: "eslint.config.mjs",
    old: 'const TRANSPORTS = ["fetch", "XMLHttpRequest", "WebSocket"];',
    new: 'const TRANSPORTS = ["fetch", "XMLHttpRequest"];',
    run: [LINT_TEST],
    expect: ["flags WebSocket in src/components/conversation/Composer.tsx"],
  },
  // T-9.8: the You tab, its settings, edit and photos screens; P-762's line.
  {
    id: "t98-web-01-her-balance-shown",
    file: "src/components/you/DeleteAccount.tsx",
    old: 'new Set(["male"])',
    new: 'new Set(["male", "female"])',
    run: ["src/components/you/SettingsScreen.test.tsx"],
    expect: ["shows her no balance"],
  },
  {
    id: "t98-web-02-one-vela-as-many",
    file: "src/components/you/DeleteAccount.tsx",
    old: "velas === 1",
    new: "velas === -1",
    run: ["src/components/you/SettingsScreen.test.tsx"],
    expect: ["says one Vela as one"],
  },
  {
    id: "t98-web-03-deleted-but-the-cache-kept",
    file: "src/lib/queries/account.ts",
    old: "      client.clear();\n",
    new: "",
    run: ["src/components/you/SettingsScreen.test.tsx"],
    expect: ["deletes, then signs the tab out"],
  },
  {
    id: "t98-web-04-no-copy-read-as-a-failure",
    file: "src/lib/queries/account.ts",
    old: 'if (error instanceof ApiError && error.code === "NOT_FOUND")\n          return null;',
    new: "void ApiError;",
    run: ["src/components/you/SettingsScreen.test.tsx"],
    expect: ["asks for one when none was ever made"],
  },
  {
    id: "t98-web-05-a-switch-sends-them-all",
    file: "src/components/you/SettingsScreen.tsx",
    old: "      { [setting]: value },",
    new: "      { ...me.profile, [setting]: value },",
    run: ["src/components/you/SettingsScreen.test.tsx"],
    expect: ["sends is_hidden alone"],
  },
  {
    id: "t98-web-06-untied-on-cancel",
    file: "src/components/you/KnotsSection.tsx",
    old: "onClick={onClose}",
    new: "onClick={() => untie.mutate(row.id)}",
    run: ["src/components/you/YouScreen.test.tsx"],
    expect: ["asks before untying"],
  },
  {
    id: "t98-web-07-the-badge-from-is-verified",
    file: "src/components/you/ProfileSummary.tsx",
    old: "<SelfieLine me={me} badge={profile.data.shows_badge} />",
    new: "<SelfieLine me={me} badge={me.is_verified} />",
    run: ["src/components/you/YouScreen.test.tsx"],
    expect: ["never the badge from is_verified alone"],
  },
  {
    id: "t98-web-08-lock-now-without-a-pin",
    file: "src/components/you/YouRows.tsx",
    old: "{me.has_pin && (",
    new: "{(me.has_pin || true) && (",
    run: ["src/components/you/YouScreen.test.tsx"],
    expect: ["offers no Lock now without a PIN"],
  },
  {
    id: "t98-web-09-his-gifts-asked-for",
    file: "src/components/you/YouScreen.tsx",
    old: "{woman && <ReceivedGifts />}",
    new: "<ReceivedGifts />",
    run: ["src/components/you/YouScreen.test.tsx"],
    expect: ["shows her gifts to her alone"],
  },
  {
    id: "t98-web-10-edit-sends-it-all",
    file: "src/components/you/EditProfile.tsx",
    old: '            value !== (me.profile[key as keyof typeof text] ?? ""),',
    new: "            value !== null,",
    run: ["src/components/you/EditProfile.test.tsx"],
    expect: ["sends only what changed"],
  },
  {
    id: "t98-web-11-a-matched-face-photo-unlocked",
    file: "src/components/you/MyPhotos.tsx",
    old: "locked={me.is_verified}",
    new: "locked={false}",
    run: ["src/components/you/MyPhotos.test.tsx"],
    expect: ["locks a matched person's face photo"],
  },
  {
    id: "t98-web-12-the-block-sheet-forgets-the-undo",
    file: "src/components/profile/BlockSheet.tsx",
    old: '  "profile.blockUndo",\n',
    new: "",
    run: ["src/components/profile/BlockSheet.test.tsx"],
    expect: ["says what a block does"],
  },
  {
    id: "t95-web-01-a-user-sees-the-panel",
    file: "src/components/admin/AdminGate.tsx",
    old: "  if (!STAFF.has(gate.me.role)) notFound();\n",
    new: "",
    run: ["src/components/admin/AdminGate.test.tsx"],
    expect: ["shows anyone else the 404 page"],
  },
  {
    id: "t95-web-02-users-are-staff",
    file: "src/components/admin/AdminGate.tsx",
    old: 'new Set(["moderator", "admin"])',
    new: 'new Set(["user", "moderator", "admin"])',
    run: ["src/components/admin/AdminGate.test.tsx"],
    expect: ["shows anyone else the 404 page"],
  },
  {
    id: "t95-web-03-the-panel-unnonced",
    file: "src/lib/security-headers.ts",
    old: '  "admin",\n] as const;',
    new: "] as const;",
    run: ["src/lib/security-headers.test.ts"],
    expect: ["has the proxy match exactly NONCE_ROUTES"],
  },
  {
    id: "t95-web-04-the-panel-built-ahead",
    file: "src/app/admin/layout.tsx",
    old: 'export const dynamic = "force-dynamic";\n',
    new: "",
    run: ["src/proxy.test.ts"],
    expect: ["force dynamic rendering"],
  },
  {
    id: "t95-web-05-confirmed-without-a-reason",
    file: "src/components/admin/ConfirmAction.tsx",
    old: "disabled={!enough || !ready}",
    new: "disabled={!ready}",
    run: ["src/components/admin/ReportQueue.test.tsx"],
    expect: ["resolves only once an action is picked"],
  },
  {
    id: "t95-web-06-a-retry-with-a-new-key",
    file: "src/components/admin/CreditsForm.tsx",
    old: "{ delta, reason, key },",
    new: "{ delta, reason, key: freshKey() },",
    run: ["src/components/admin/UserDetail.test.tsx"],
    expect: ["the same on a retry"],
  },
  {
    id: "t95-web-07-a-moderator-offered-a-ban",
    file: "src/components/admin/ReportQueue.tsx",
    old: 'isAdmin || choice !== "ban"',
    new: "true",
    run: ["src/components/admin/ReportQueue.test.tsx"],
    expect: ["never offers a moderator a ban"],
  },
  {
    id: "t95-web-08-a-chat-read-before-why",
    file: "src/lib/queries/admin.ts",
    old: "    enabled: reason !== null,\n",
    new: "",
    run: ["src/components/admin/ThreadReader.test.tsx"],
    expect: ["asks nothing until staff say why"],
  },
  {
    id: "t95-web-09-reads-again-on-focus",
    file: "src/lib/queries/admin.ts",
    old: "  refetchOnWindowFocus: false,\n",
    new: "  refetchOnWindowFocus: true,\n",
    run: ["src/components/admin/MetricTiles.test.tsx"],
    expect: ["never asks again by itself"],
  },
  {
    id: "t95-web-10-claims-for-a-moderator",
    file: "src/components/admin/AdminFrame.tsx",
    old: "isAdmin || !section.adminOnly",
    new: "true",
    run: ["src/components/admin/AdminFrame.test.tsx"],
    expect: ["keeps claims an admin's"],
  },
  {
    id: "t95-web-11-a-moderator-offered-velas",
    file: "src/components/admin/UserDetail.tsx",
    old: '{isAdmin && user.gender === "male" && !user.erased && (',
    new: '{user.gender === "male" && !user.erased && (',
    run: ["src/components/admin/UserDetail.test.tsx"],
    expect: ["no ban nor Velas"],
  },
  {
    id: "t95-web-12-no-review-promised",
    file: "src/i18n/en.ts",
    old: '      "A moderator reviews this within 24 hours. They\'re never told who reported them, and nothing you wrote appears on their profile.",',
    new: '      "They\'re never told who reported them, and nothing you wrote appears on their profile.",',
    run: ["src/components/profile/ReportSheet.test.tsx"],
    expect: ["asks for a reason first", "promises only the queue's 24 hours"],
  },
  {
    id: "p850-web-01-a-code-sent-while-restoring",
    file: "src/components/onboarding/SignIn.tsx",
    old: '  const canSend = restore === "signed-out" || restore === "failed";\n',
    new: "  const canSend = restore !== undefined;\n",
    run: ["src/app/(auth)/login/page.test.tsx"],
    expect: [
      "sends nothing while the restore is on its way",
      "never sends for someone whose session restores",
    ],
  },
  {
    id: "p850-web-02-no-signal-shuts-sign-in",
    file: "src/components/onboarding/SignIn.tsx",
    old: '  const canSend = restore === "signed-out" || restore === "failed";\n',
    new: '  const canSend = restore === "signed-out";\n',
    run: ["src/app/(auth)/login/page.test.tsx"],
    expect: [
      "still sends when the restore failed for no signal",
      "still sends when the restore failed for a 503",
    ],
  },
  {
    // CI's run of 16 October 2026 at 00:02 UTC: a Knot tied 10 minutes before
    // was yesterday's, so the pin is what keeps the test to its claim.
    id: "p856-web-01-the-knot-test-just-after-midnight",
    file: "src/components/conversation/ConversationScreen.test.tsx",
    old: "    midday.setHours(12, 0, 0, 0);\n",
    new: "    midday.setHours(0, 2, 30, 0);\n",
    run: ["src/components/conversation/ConversationScreen.test.tsx"],
    expect: ["shows a Knot as permanent"],
  },
];

const WEB = join(import.meta.dirname, "..");

function sha(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

/** Every changed or new file in the tree and its SHA-256, to prove nothing stayed. */
function tree(): string {
  const listed = spawnSync(
    "git",
    ["ls-files", "-m", "-o", "--exclude-standard", "--full-name"],
    { cwd: WEB, encoding: "utf8" },
  ).stdout;
  const root = spawnSync("git", ["rev-parse", "--show-toplevel"], {
    cwd: WEB,
    encoding: "utf8",
  }).stdout.trim();
  return listed
    .split("\n")
    .filter(Boolean)
    .sort()
    .map((file) => `${file} ${sha(join(root, file))}`)
    .join("\n");
}

function runCase(found: BreakCase) {
  const path = join(WEB, found.file);
  const original = readFileSync(path);
  const before = sha(path);
  const text = original.toString("utf8");
  if (text.split(found.old).length !== 2) {
    throw new Error(
      `${found.id}: its anchor in ${found.file} is gone or ambiguous`,
    );
  }
  writeFileSync(
    path,
    text.replace(found.old, () => found.new),
  );
  let output = "";
  let status: number | null = null;
  try {
    const run = spawnSync("pnpm", ["exec", "vitest", "run", ...found.run], {
      cwd: WEB,
      encoding: "utf8",
    });
    output = run.stdout + run.stderr;
    status = run.status;
  } finally {
    writeFileSync(path, original);
  }
  const failedLines = output.split("\n").filter((line) => /×|FAIL/.test(line));
  const missing = found.expect.filter(
    (name) => !failedLines.some((line) => line.includes(name)),
  );
  return {
    id: found.id,
    red: status !== 0 && missing.length === 0,
    exit: status,
    missing,
    restored: sha(path) === before,
  };
}

function main(prefixes: string[]): number {
  const chosen = CASES.filter(
    (c) => prefixes.length === 0 || prefixes.some((p) => c.id.startsWith(p)),
  );
  const start = tree();
  let failures = 0;
  for (const found of chosen) {
    const result = runCase(found);
    if (!result.red || !result.restored) failures += 1;
    process.stdout.write(`${JSON.stringify(result)}\n`);
  }
  const same = tree() === start;
  process.stdout.write(
    `${chosen.length - failures} of ${chosen.length} red and restored; ` +
      `the tree ${same ? "is byte for byte as it was" : "CHANGED"}\n`,
  );
  return failures === 0 && same ? 0 : 1;
}

if (import.meta.main) {
  process.exitCode = main(process.argv.slice(2));
}
