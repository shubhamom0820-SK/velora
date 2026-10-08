import type { Metadata } from "next";
import { cache } from "react";

import { SharedProfileView } from "@/components/share/SharedProfileView";
import { SignedInProfileRedirect } from "@/components/share/SignedInProfileRedirect";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";
import { getSharedProfile } from "@/lib/queries/profiles";

/**
 * Asked once per request, for the title and the page alike. A refusal of any
 * kind, a rate limit's among them, shows the page as not public: never an
 * error page, and never anything of theirs.
 */
const shared = cache(async (username: string) => {
  try {
    return await getSharedProfile(username);
  } catch (error) {
    if (error instanceof ApiError) return null;
    throw error;
  }
});

export async function generateMetadata({
  params,
}: PageProps<"/share/[username]">): Promise<Metadata> {
  const { username } = await params;
  const found = await shared(username);
  return {
    title: found
      ? t("share.title", { name: found.first_name, app: APP_NAME })
      : t("share.unavailable"),
    alternates: { canonical: `/@${username}` },
  };
}

/** `/@username` (T-6.8, D-001, D-544), reached through next.config's rewrite. */
export default async function SharePage({
  params,
}: PageProps<"/share/[username]">) {
  const { username } = await params;
  return (
    <>
      <SignedInProfileRedirect username={username} />
      <SharedProfileView shared={await shared(username)} />
    </>
  );
}
