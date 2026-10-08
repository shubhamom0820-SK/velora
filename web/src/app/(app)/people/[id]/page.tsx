import type { Metadata } from "next";

import { ProfileScreen } from "@/components/profile/ProfileScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("profile.title") };

/**
 * A person's profile in the app (T-6.8), the one route a profile has (agreed
 * with T-6.5's session, 8 October 2026): the deck's tap (T-6.5), search's
 * rows (T-6.6) and Liked you's tiles (T-6.7) all lead here, and `/@username`
 * sends someone signed in here too.
 */
export default async function PersonPage({
  params,
}: PageProps<"/people/[id]">) {
  const { id } = await params;
  return <ProfileScreen id={id} />;
}
