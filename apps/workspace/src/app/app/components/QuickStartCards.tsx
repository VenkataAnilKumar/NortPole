"use client";

import { useState, type ReactNode } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface QuickStart {
  id: string;
  label: string;
  prompt: string;
  // When set, the card opens this page instead of filling the composer.
  href?: string;
  // When set, the card starts a draft task from this Everyday workflow.
  workflow?: { pack: string; template: string };
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
    id: "workflows",
    label: "Browse workflows",
    prompt: "",
    href: "/app/packs",
    icon: (
      <svg {...ICON_PROPS} stroke="#e89a1a">
        <path d="M3 7l9-4 9 4-9 4zM3 12l9 4 9-4M3 17l9 4 9-4" />
      </svg>
    ),
  },
];

/**
 * Quick-start cards under the home greeting. Picking one puts a starter
 * prompt in the composer (nothing is sent until the user submits it), or
 * opens the Workflows page.
 */
interface PackSummary {
  pack_id: string;
  group?: string;
  ready_on_current_route: boolean;
  templates: { id: string; title: string }[];
}

/** Up to three workflows from Everyday packs that can run now, else the built-in starters. */
function useStarters(): QuickStart[] {
  const { data } = useSWR<PackSummary[]>("/api/packs", errorHandlingFetcher);
  const builtIn = QUICK_STARTS.filter((q) => !q.href);
  const browse = QUICK_STARTS.filter((q) => q.href);
  const everyday = (data ?? [])
    .filter((p) => p.group === "everyday" && p.ready_on_current_route)
    .flatMap((p) => p.templates.map((t) => ({ pack: p.pack_id, template: t.id, title: t.title })))
    .slice(0, 3);
  if (everyday.length === 0) return QUICK_STARTS;
  return [
    ...everyday.map((w, i) => ({
      id: `wf-${w.pack}-${w.template}`,
      label: w.title,
      prompt: "",
      workflow: { pack: w.pack, template: w.template },
      icon: builtIn[i % builtIn.length]?.icon ?? null,
    })),
    ...browse,
  ];
}

/**
 * Quick-start cards under the home greeting. A card either starts a draft task from an Everyday workflow (nothing
 * runs until its owner presses Start), puts a starter prompt in the composer (nothing is sent until the user submits
 * it), or opens the Workflows page. Without an Everyday pack that can run on the current model, the built-in
 * starters are shown.
 */
export default function QuickStartCards({
  onPick,
}: {
  onPick: (prompt: string) => void;
}) {
  const starters = useStarters();
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const startWorkflow = async (q: QuickStart) => {
    if (!q.workflow) return;
    setBusy(q.id);
    setFailed(null);
    const res = await fetch(`/api/packs/${q.workflow.pack}/templates/${q.workflow.template}/task`, { method: "POST" });
    if (!res.ok) {
      setBusy(null);
      setFailed("That workflow could not start a draft right now. Try it from the Workflows page.");
      return;
    }
    const created = (await res.json()) as { id: string };
    window.location.assign(`/app/reviewed-tasks?task=${encodeURIComponent(created.id)}`);
  };

  const cls =
    "flex min-h-14 flex-row items-center gap-3 rounded-2xl border border-border-01 bg-background-neutral-00 p-3 sm:min-h-28 sm:flex-col sm:items-start sm:justify-between sm:gap-6 sm:p-4 text-left text-sm font-medium text-text-05 shadow-sm transition-colors hover:bg-background-neutral-01 disabled:opacity-60";
  return (
    <div className="flex w-full flex-col gap-2">
      <div data-testid="quick-start-cards" className="grid w-full grid-cols-2 gap-3 pt-4 sm:grid-cols-4 sm:pt-6">
        {starters.map((q) =>
          q.href ? (
            <a key={q.id} href={q.href} className={cls}>
              {q.icon}
              {q.label}
            </a>
          ) : (
            <button
              key={q.id}
              type="button"
              data-kind={q.workflow ? "workflow" : "builtin"}
              disabled={busy !== null}
              onClick={() => (q.workflow ? startWorkflow(q) : onPick(q.prompt))}
              className={cls}
            >
              {q.icon}
              {busy === q.id ? "Starting…" : q.label}
            </button>
          )
        )}
      </div>
      {failed && <p role="alert" className="text-sm text-status-text-error-05">{failed}</p>}
    </div>
  );
}
