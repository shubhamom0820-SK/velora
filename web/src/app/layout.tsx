import type { Metadata, Viewport } from "next";

import { ServiceWorkerRegistrar } from "@/components/pwa/ServiceWorkerRegistrar";
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
        {/* The PWA's worker, the push one (T-9.7, D-1041), on every page. */}
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
