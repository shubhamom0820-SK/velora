import { SignIn } from "@/components/onboarding/SignIn";
import { SignedInRedirect } from "@/components/session/SignedInRedirect";

/** Sign-in (T-3.11). A session that restores moves on to its step (T-3.10). */
export default function LoginPage() {
  return (
    <>
      <SignedInRedirect />
      <SignIn />
    </>
  );
}
