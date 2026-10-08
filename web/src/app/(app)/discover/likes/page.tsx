import type { Metadata } from "next";

import { LikedYouScreen } from "@/components/likes/LikedYouScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("likes.title") };

/** Liked you (T-6.7). T-6.5's deck links here, with the count (P-443). */
export default function LikedYouPage() {
  return <LikedYouScreen />;
}
