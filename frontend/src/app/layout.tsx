import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Geist_Mono, Manrope } from "next/font/google";
import { AppSidebar, BottomNav } from "@/components/BottomNav";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import "./globals.css";

const manrope = Manrope({ variable: "--font-manrope", subsets: ["latin", "cyrillic"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "T-Port — One Destination. Every Way to Get There.", template: "%s · T-Port" },
  description:
    "Compare trains, buses, flights and taxis across Uzbekistan. Transparent sources, no invented fares.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#050C1F" },
    { media: "(prefers-color-scheme: light)", color: "#F4F1E7" },
  ],
};

/**
 * Runs before first paint so nothing flashes: applies the saved theme (or the system one), the
 * interface language (saved, else the browser's: en / uz / ru), and decides whether the landing
 * page's short intro plays (first visit to "/" in this browser session, motion allowed).
 */
const BOOT_SCRIPT = `(function(){var d=document.documentElement;try{var p=localStorage.getItem("tport.theme")||"system";d.dataset.theme=p==="system"?(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"):p}catch(e){}try{var l=localStorage.getItem("tport.lang");if(!l){var n=(navigator.languages||[navigator.language||""]).join(",").toLowerCase();l=/(^|,)uz/.test(n)?"uz":/(^|,)ru/.test(n)?"ru":"en"}if(l==="en"||l==="uz"||l==="ru")d.lang=l}catch(e){}try{if(location.pathname==="/"&&!sessionStorage.getItem("tport.intro")){sessionStorage.setItem("tport.intro","1");if(!matchMedia("(prefers-reduced-motion: reduce)").matches)d.dataset.intro="play"}}catch(e){}})()`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: BOOT_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-blue focus:px-4 focus:py-2 focus:text-white"
        >
          Skip to content
        </a>
        <SiteHeader />
        {/* Extra bottom space on phones so the floating nav never covers content. */}
        <div className="mx-auto flex w-full max-w-[96rem] flex-1 gap-6 px-0 lg:px-6 lg:pt-6">
          <Suspense fallback={null}>
            <AppSidebar />
          </Suspense>
          <main id="main" className="min-w-0 flex-1 pb-28 md:pb-0">
            {children}
          </main>
        </div>
        <SiteFooter />
        {/* The nav reads the current path, which is only known at request time. */}
        <Suspense fallback={null}>
          <BottomNav />
        </Suspense>
      </body>
    </html>
  );
}
