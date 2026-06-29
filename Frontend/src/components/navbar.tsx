"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/rankings", label: "Candidates" },
  { href: "/analytics", label: "Analytics" },
  { href: "/demo", label: "Demo" },
  { href: "/intake", label: "Intake" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="fixed top-0 w-full z-50 bg-surface/40 backdrop-blur-xl border-b border-white/5 flex justify-between items-center px-margin-mobile md:px-margin-desktop py-4">
      <div className="flex items-center gap-8">
        <Link href="/" className="flex items-center gap-2">
          <span className="font-headline-lg text-lg text-white/90 tracking-tighter">
            FHire
          </span>
        </Link>
        <div className="hidden md:flex gap-6">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "font-label-sm text-xs uppercase tracking-wider cursor-pointer transition-all duration-200 active:scale-95",
                pathname === item.href
                  ? "text-tertiary border-b border-tertiary/50 pb-1"
                  : "text-on-surface-variant hover:text-white"
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-4">
        <Link
          href="/rankings"
          className="frozen-glow px-4 py-1.5 rounded font-label-sm text-xs uppercase tracking-wider text-white hover:scale-105 active:scale-95 transition-all"
        >
          Explore Rankings
        </Link>
      </div>
    </nav>
  );
}
