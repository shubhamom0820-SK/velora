import type { Metadata } from "next";

import { MyPhotos } from "@/components/you/MyPhotos";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("you.photos") };

/** Your photos (T-9.8, D-910), linked from You. */
export default function MyPhotosPage() {
  return <MyPhotos />;
}
