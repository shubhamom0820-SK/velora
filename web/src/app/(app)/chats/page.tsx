import type { Metadata } from "next";

import { ChatsScreen } from "@/components/chats/ChatsScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("chats.title") };

/** The chats list (T-7.10), inside the app shell's `<main>` (T-5.6). */
export default function ChatsPage() {
  return <ChatsScreen />;
}
