"use client";

import type { ReactNode } from "react";

interface QuickStart {
  id: string;
  label: string;
  prompt: string;
  icon: ReactNode;
}

const ICON_PROPS = {
  width: 26,
  height: 26,
  viewBox: "0 0 24 24",
  fill: "none",
  strokeWidth: 1.8,
  "aria-hidden": true,
} as const;

const QUICK_STARTS: QuickStart[] = [
  {
    id: "brief",
    label: "Draft a cited brief",
    prompt: "Draft a cited brief on: ",
    icon: (
      <svg {...ICON_PROPS} stroke="#3b82f6">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M10 13l-2 2 2 2M14 13l2 2-2 2" />
      </svg>
    ),
  },
  {
    id: "compare",
    label: "Compare documents",
    prompt: "Compare these documents and list what changed, with citations: ",
    icon: (
      <svg {...ICON_PROPS} stroke="#ef6a6a">
        <rect x="3" y="4" width="8" height="16" rx="1.5" />
        <rect x="13" y="4" width="8" height="16" rx="1.5" />
      </svg>
    ),
  },
  {
    id: "policy",
    label: "Find a policy",
    prompt: "Find the policy that covers: ",
    icon: (
      <svg {...ICON_PROPS} stroke="#22a05a">
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-5-5" />
      </svg>
    ),
  },
  {
    id: "pack",
    label: "Use a vertical pack",
    prompt: "Use the vertical pack to help with: ",
    icon: (
      <svg {...ICON_PROPS} stroke="#e89a1a">
        <path d="M3 7l9-4 9 4-9 4zM3 12l9 4 9-4M3 17l9 4 9-4" />
      </svg>
    ),
  },
];

/**
 * Quick-start cards under the home greeting. Picking one puts a starter
 * prompt in the composer; nothing is sent until the user submits it.
 */
export default function QuickStartCards({
  onPick,
}: {
  onPick: (prompt: string) => void;
}) {
  return (
    <div
      data-testid="quick-start-cards"
      className="grid w-full grid-cols-2 gap-3 pt-4 sm:grid-cols-4 sm:pt-6"
    >
      {QUICK_STARTS.map((q) => (
        <button
          key={q.id}
          type="button"
          onClick={() => onPick(q.prompt)}
          className="flex min-h-14 flex-row items-center gap-3 rounded-2xl border border-border-01 bg-background-neutral-00 p-3 sm:min-h-28 sm:flex-col sm:items-start sm:justify-between sm:gap-6 sm:p-4 text-left text-sm font-medium text-text-05 shadow-sm transition-colors hover:bg-background-neutral-01"
        >
          {q.icon}
          {q.label}
        </button>
      ))}
    </div>
  );
}
