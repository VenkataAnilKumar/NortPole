"use client";

import { NavLink } from "@opal/navigation";
import type { Route } from "next";
import { usePathname } from "@opal/navigation";

export interface SectionTab {
  href: string;
  label: string;
  matchDescendants?: boolean;
}

/**
 * The tab row at the top of a sidebar section with several pages (Workflows, Sources). Each tab is a link, so a page
 * can be bookmarked or opened in a new tab; the current one is marked for screen readers with aria-current.
 */
export default function SectionTabs({ label, tabs }: { label: string; tabs: SectionTab[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="mx-auto w-full max-w-5xl px-4 pt-4 sm:px-8 sm:pt-6" data-testid="section-tabs">
      <ul className="flex gap-1 overflow-x-auto border-b border-border-01">
        {tabs.map((t) => {
          const current = pathname === t.href
            ? "page"
            : t.matchDescendants && pathname?.startsWith(`${t.href}/`)
              ? "location"
              : undefined;
          return (
            <li key={t.href} className="shrink-0">
              <NavLink
                href={t.href as Route}
                aria-current={current}
                className={`inline-flex min-h-11 items-center border-b-2 px-3 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] ${
                  current ? "border-text-05 text-text-05" : "border-transparent text-text-03 hover:text-text-05"
                }`}
              >
                {t.label}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
