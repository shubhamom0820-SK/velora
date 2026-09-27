import type { Metadata, Viewport } from "next";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { THEME_COLOR } from "@/styles/theme-color";

import "./globals.css";

export const metadata: Metadata = {
  title: APP_NAME,
  description: t("meta.description"),
};

export const viewport: Viewport = {
  themeColor: THEME_COLOR,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
