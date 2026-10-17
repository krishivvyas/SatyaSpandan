import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SatyaSpandan · The Pulse of Truth",
  description:
    "Explainable deepfake warning signs from facial blood-flow (rPPG) coherence. Cyber Samvad Hackathon 2026, Problem Statement 1.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${mono.variable} h-full antialiased`}>
      {/* suppressHydrationWarning: browser extensions (e.g. ColorZilla's cz-shortcut-listen) add attributes to <body> */}
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <Providers>
          <SiteHeader />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-10">{children}</main>
          <footer className="border-t border-border py-6 text-center text-xs text-muted px-4">
            SatyaSpandan · Cyber Samvad Hackathon 2026 · Problem Statement 1 “Is This Video Real?” · Results are warning
            signs, not proof. Uploaded videos are deleted after analysis.
          </footer>
        </Providers>
      </body>
    </html>
  );
}
