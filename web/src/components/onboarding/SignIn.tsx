"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Phone } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { ButtonLink } from "@/components/ui/ButtonLink";
import { Icon } from "@/components/ui/Icon";
import { OtpInput } from "@/components/ui/OtpInput";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import {
  useFirebaseSendCode,
  useFirebaseVerifyCode,
  useSendCode,
  useVerifyCode,
} from "@/lib/queries/onboarding";
import { signInOpen, signInPath } from "@/lib/sign-in-path";
import { useSession } from "@/store/session";
import { z } from "@/lib/zod";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useFirebasePhone } from "./useFirebasePhone";

/**
 * The ten digits of an Indian mobile number as people type or paste it: with
 * spaces, a leading 0, or +91. Only the shape; whether it's a mobile is the
 * server's to say (D-070, D-082).
 */
export function tenDigits(typed: string): string {
  const digits = typed.replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) return digits.slice(2);
  if (digits.length === 11 && digits.startsWith("0")) return digits.slice(1);
  return digits;
}

const phoneForm = z.object({
  phone: z.string().refine((typed) => /^[0-9]{10}$/.test(tenDigits(typed))),
});

/**
 * /login (T-3.11, T-3.14). The path follows the build (D-081): Path B where
 * `APP_ENV` is local or ci, Firebase on staging and production, on the same
 * two screens. A build with neither says sign-in isn't open yet. After an
 * under-18 date of birth, it says what happened (D-079, D-072).
 */
export function SignIn() {
  const farewell = useSession((state) => state.farewell);
  if (farewell === "underage") return <Underage />;
  if (!signInOpen()) return <SignInClosed />;
  return signInPath() === "firebase" ? <FirebaseSignIn /> : <PathBSignIn />;
}

function Underage() {
  return (
    <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-title-1">
        {t("onboarding.underage.title", { app: APP_NAME })}
      </h1>
      <p className="text-body text-mute max-w-[520px]">
        {t("onboarding.underage.body")}
      </p>
    </main>
  );
}

export function SignInClosed() {
  return (
    <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-title-1">{t("onboarding.closed.title")}</h1>
      <p className="text-body text-mute max-w-[520px]">
        {t("onboarding.closed.body", { app: APP_NAME })}
      </p>
      <ButtonLink href="/#waitlist" className="mt-3">
        {t("onboarding.closed.waitlist")}
      </ButtonLink>
    </main>
  );
}

/** Texts a code, and says when another may be asked for. */
type SendCode = ReturnType<typeof useSendCode>;
/** Checks the code; on success the session has started. */
type VerifyCode = ReturnType<typeof useVerifyCode>;

/** Path B (T-3.11): our API sends the code and checks it. */
function PathBSignIn() {
  const send = useSendCode();
  const verify = useVerifyCode();
  return <CodeSignIn send={send} verify={verify} namesGoogle={false} />;
}

/**
 * Path A (T-3.14): Firebase sends the code and checks it, and our API
 * exchanges its token for our session (D-085). reCAPTCHA's invisible widget
 * renders into the element below, as the screen opens.
 */
function FirebaseSignIn() {
  const recaptcha = useRef<HTMLDivElement>(null);
  const firebase = useFirebasePhone(recaptcha);
  const send = useFirebaseSendCode(firebase);
  const verify = useFirebaseVerifyCode(firebase);
  return (
    <>
      <CodeSignIn send={send} verify={verify} namesGoogle />
      <div ref={recaptcha} />
    </>
  );
}

type Stage =
  { kind: "phone" } | { kind: "code"; phone: string; resendAt: number };

function CodeSignIn({
  send,
  verify,
  namesGoogle,
}: {
  send: SendCode;
  verify: VerifyCode;
  namesGoogle: boolean;
}) {
  // The number stays here, in memory: never a URL (D-080, rule 15).
  const [stage, setStage] = useState<Stage>({ kind: "phone" });
  return stage.kind === "phone" ? (
    <PhoneStage
      send={send}
      namesGoogle={namesGoogle}
      onSent={(phone, resendAfterS) =>
        setStage({
          kind: "code",
          phone,
          resendAt: Date.now() + resendAfterS * 1000,
        })
      }
    />
  ) : (
    <CodeStage
      send={send}
      verify={verify}
      phone={stage.phone}
      resendAt={stage.resendAt}
      onResent={(resendAfterS) =>
        setStage({ ...stage, resendAt: Date.now() + resendAfterS * 1000 })
      }
      onChangeNumber={() => {
        send.reset();
        verify.reset();
        setStage({ kind: "phone" });
      }}
    />
  );
}

function PhoneStage({
  send,
  namesGoogle,
  onSent,
}: {
  send: SendCode;
  namesGoogle: boolean;
  onSent: (phone: string, resendAfterS: number) => void;
}) {
  const form = useForm({
    resolver: zodResolver(phoneForm),
    mode: "onChange",
    defaultValues: { phone: "" },
  });
  const copy = send.isError ? errorCopy(send.error) : null;

  const submit = form.handleSubmit(({ phone }) => {
    const e164 = `+91${tenDigits(phone)}`;
    send.mutate(e164, {
      onSuccess: ({ resend_after_s }) => onSent(e164, resend_after_s),
    });
  });

  return (
    <form onSubmit={submit} noValidate>
      <StepFrame
        index={0}
        title={t("onboarding.phone.title")}
        sub={t("onboarding.phone.sub")}
        footer={
          <>
            <Button
              type="submit"
              fullWidth
              loading={send.isPending}
              disabled={!form.formState.isValid}
            >
              {t("onboarding.phone.send")}
            </Button>
            {namesGoogle && <GoogleConsent />}
          </>
        }
      >
        <label className="text-small text-mute" htmlFor="phone">
          {t("onboarding.phone.label")}
        </label>
        <div className="rounded-input border-line bg-surface focus-within:border-accent mt-1.5 flex items-center gap-2 border px-4 py-3.5">
          <Icon icon={Phone} size={16} className="text-mute" />
          <span className="text-input text-ink">
            {t("onboarding.phone.prefix")}
          </span>
          <input
            id="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            autoFocus
            placeholder={t("onboarding.phone.placeholder")}
            aria-invalid={copy?.fields.phone ? true : undefined}
            className="text-input text-ink placeholder:text-mute min-w-0 flex-1 bg-transparent outline-none"
            {...form.register("phone")}
          />
        </div>
        {copy?.fields.phone ? (
          <p role="alert" className="text-small text-accent mt-3">
            {copy.fields.phone}
          </p>
        ) : (
          <FormError copy={copy} />
        )}
      </StepFrame>
    </form>
  );
}

/**
 * Firebase asks apps to get consent before a number goes to Google (its phone
 * sign-in docs), so the line is there before "Send code" is tapped, worded as
 * /privacy puts it (D-048). Only on Firebase builds: on Path B, Google sends
 * nothing, and the line would be false (D-081).
 */
function GoogleConsent() {
  return (
    <p className="text-small text-mute mt-3 text-center">
      {t("onboarding.phone.googleConsent")}{" "}
      <Link href="/privacy" className="underline underline-offset-2">
        {t("onboarding.phone.googleConsentLink")}
      </Link>
    </p>
  );
}

function useSecondsUntil(at: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return Math.max(0, Math.ceil((at - now) / 1000));
}

function CodeStage({
  send: resend,
  verify,
  phone,
  resendAt,
  onResent,
  onChangeNumber,
}: {
  send: SendCode;
  verify: VerifyCode;
  phone: string;
  resendAt: number;
  onResent: (resendAfterS: number) => void;
  onChangeNumber: () => void;
}) {
  const [code, setCode] = useState("");
  const seconds = useSecondsUntil(resendAt);
  const failure = verify.error ?? resend.error;
  const copy = failure ? errorCopy(failure) : null;

  function submit(otp: string) {
    if (verify.isPending) return;
    // On success the session starts; /login's redirect takes it from there.
    verify.mutate({ phone, otp }, { onError: () => setCode("") });
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (code.length === 6) submit(code);
      }}
    >
      <StepFrame
        index={1}
        title={t("onboarding.code.title")}
        sub={t("onboarding.code.sub", { phone: phone.slice(3) })}
        back={onChangeNumber}
        footer={
          <>
            <Button
              type="submit"
              fullWidth
              loading={verify.isPending}
              disabled={code.length !== 6}
            >
              {t("onboarding.code.verify")}
            </Button>
            <div className="text-small text-mute mt-3 text-center">
              {seconds > 0 ? (
                t("onboarding.code.resendIn", { seconds })
              ) : (
                <button
                  type="button"
                  className="text-accent underline underline-offset-2"
                  onClick={() => {
                    verify.reset();
                    resend.mutate(phone, {
                      onSuccess: ({ resend_after_s }) =>
                        onResent(resend_after_s),
                    });
                  }}
                >
                  {t("onboarding.code.resend")}
                </button>
              )}
            </div>
          </>
        }
      >
        <OtpInput
          label={t("onboarding.code.label")}
          value={code}
          onChange={setCode}
          onComplete={submit}
          invalid={copy !== null}
          disabled={verify.isPending}
          autoFocus
        />
        <FormError copy={copy} />
      </StepFrame>
    </form>
  );
}
