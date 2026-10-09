import type { Metadata } from "next";

import { ConversationScreen } from "@/components/conversation/ConversationScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("conversation.title") };

/**
 * One conversation (T-7.11), opened from a row of the chats list (T-7.10),
 * inside the app shell's `<main>` (T-5.6), under the nonce routes' CSP: it
 * renders the other person's text (D-541).
 */
export default async function ConversationPage({
  params,
}: PageProps<"/chats/[id]">) {
  const { id } = await params;
  return <ConversationScreen id={id} />;
}
