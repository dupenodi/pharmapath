"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Assistant" },
  { href: "/graph", label: "Supply Map" },
];

export default function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-1 border-b border-zinc-800 bg-zinc-950/80 px-4 py-2 backdrop-blur">
      <span className="mr-4 text-sm font-semibold tracking-tight text-zinc-100">EaseMed</span>
      {TABS.map((tab) => {
        const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
              active
                ? "bg-zinc-100 font-medium text-zinc-900"
                : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
