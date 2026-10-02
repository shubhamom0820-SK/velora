import type { Metadata, Viewport } from "next";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { QueryProvider } from "@/lib/queries/QueryProvider";
import { rootMetadata } from "@/lib/site";
import { THEME_COLOR } from "@/styles/theme-color";

import "./globals.css";

// Titles, the share preview, and `noindex` everywhere but production (T-2.4).
export const metadata: Metadata = rootMetadata();

export const viewport: Viewport = {
  themeColor: THEME_COLOR,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <ToastProvider>{children}</ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
