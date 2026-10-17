"use client";

import Link from "next/link";
import { Suspense } from "react";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { APP_NAME, TAGLINE } from "@/lib/copy";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Analyse", short: "Analyse" },
  { href: "/how-it-works", label: "How it works", short: "Science" },
  { href: "/evaluate", label: "Accuracy", short: "Accuracy" },
  { href: "/limitations", label: "Limitations", short: "Limits" },
];

export function PulseMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <path d="M4 17h6l2.5-6 4 12 3-9 1.8 3H28" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SiteHeader() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <header className="sticky top-0 z-40 h-14 border-b border-border bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-full max-w-6xl items-center gap-2 px-4">
        <Link href="/" className="flex items-center gap-2 font-bold">
          <PulseMark className="size-7" />
          <span className="hidden min-[420px]:inline">{APP_NAME}</span>
          <span className="hidden md:inline text-sm font-normal text-muted">· {TAGLINE}</span>
        </Link>
        <nav className="ml-auto flex items-center gap-0.5 text-sm">
          <Suspense fallback={<NavLinks pathname={null} />}>
            <ActiveNavLinks />
          </Suspense>
          <button
            type="button"
            aria-label="Toggle dark mode"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            className="ml-1 rounded-md p-2 text-muted hover:text-fg"
          >
            <Sun className="size-4 hidden dark:block" aria-hidden />
            <Moon className="size-4 dark:hidden" aria-hidden />
          </button>
        </nav>
      </div>
    </header>
  );
}

function ActiveNavLinks() {
  return <NavLinks pathname={usePathname()} />;
}

function NavLinks({ pathname }: { pathname: string | null }) {
  return NAV.map((n) => (
    <Link
      key={n.href}
      href={n.href}
      className={cn("whitespace-nowrap rounded-md px-1.5 py-1.5 sm:px-3", pathname === n.href ? "text-fg font-medium" : "text-muted hover:text-fg")}
    >
      <span className="sm:hidden">{n.short}</span>
      <span className="hidden sm:inline">{n.label}</span>
    </Link>
  ));
}
