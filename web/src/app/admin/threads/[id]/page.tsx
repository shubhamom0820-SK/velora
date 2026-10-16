import type { Metadata } from "next";

import { ThreadReader } from "@/components/admin/ThreadReader";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.thread.title") };

/**
 * A chat as staff read it (D-924), after saying why. From a report, `?report=`
 * starts the reason with it.
 */
export default async function AdminThreadPage({
  params,
  searchParams,
}: PageProps<"/admin/threads/[id]">) {
  const { id } = await params;
  const { report } = await searchParams;
  return (
    <ThreadReader
      id={id}
      reportId={typeof report === "string" ? report : undefined}
    />
  );
}
