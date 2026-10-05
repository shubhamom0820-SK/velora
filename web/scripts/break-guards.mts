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

const HEADERS = "src/lib/security-headers.ts";
const CONNECT = "connect: ` ${storage.privateBucket}`,";
const IMG = "img: ` blob: ${storage.privateBucket} ${storage.cdn}`,";
const EXACT_LOCAL = "adds exactly the local S3's photo sources";
const EXACT_R2 = "this environment's photo storage (T-4.6) on a Firebase build";

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
    old: 'const TRANSPORTS = ["fetch", "XMLHttpRequest"];',
    new: 'const TRANSPORTS = ["fetch"];',
    run: [LINT_TEST],
    expect: [
      "flags XMLHttpRequest in src/components/onboarding/PhotosStep.tsx",
    ],
  },
  {
    id: "t46-lint-02-fetch-allowed-outside-lib",
    file: "eslint.config.mjs",
    old: 'const TRANSPORTS = ["fetch", "XMLHttpRequest"];',
    new: 'const TRANSPORTS = ["XMLHttpRequest"];',
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
    old: '        await api\n          .delete("/v1/photos/{photo_id}", { params: { photo_id } })\n          .catch(() => undefined);\n',
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
    old: '    selfieMatched: "Selfie matches photos",',
    new: '    selfieMatched: "Verified",',
    run: [CLAIMS_TEST],
    expect: ["says none of the claims anywhere but the two named keys"],
  },
  {
    id: "t45-copy-02-the-landing-page-says-verification",
    file: "src/i18n/en.ts",
    old: '        body: "Selfies compared with profile photos, and every photo checked.",',
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
    old: 'import { ScanFace } from "lucide-react";',
    new: 'import { Shield as ScanFace } from "lucide-react";',
    run: ["src/components/ui/Avatar.test.tsx"],
    expect: ["marks a matched selfie with a face, never a shield"],
  },

  // --- T-4.7: the selfie step ---
  {
    id: "t47-camera-01-still-denied",
    file: HEADERS,
    old: '"camera=(self), microphone=(), geolocation=(self), browsing-topics=()",',
    new: '"camera=(), microphone=(), geolocation=(self), browsing-topics=()",',
    run: [CSP_TEST],
    expect: ["allow the camera (T-4.7) and location (T-4.10)"],
  },
  {
    id: "t47-camera-02-any-site",
    file: HEADERS,
    old: '"camera=(self), microphone=(), geolocation=(self), browsing-topics=()",',
    new: '"camera=*, microphone=(), geolocation=(self), browsing-topics=()",',
    run: [CSP_TEST],
    expect: ["allow the camera (T-4.7) and location (T-4.10)"],
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
    old: '      matched: "Your selfie matches your photos.",',
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
