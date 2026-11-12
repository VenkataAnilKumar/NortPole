"use client";

import { useState } from "react";
import useSWRInfinite from "swr/infinite";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Row {
  id: number;
  created_at: string;
  action: string;
  outcome: "success" | "failure" | "denied";
  actor_email: string | null;
  resource_type: string | null;
  resource_id: string | null;
  summary: string;
  details: Record<string, unknown> | null;
}
interface Page {
  events: Row[];
  next_before_id: number | null;
  actions: string[];
}

const AREAS: { label: string; prefix: string }[] = [
  { label: "Everything", prefix: "" },
  { label: "Model routes and policy", prefix: "route" },
  { label: "Tasks", prefix: "task." },
  { label: "Actions and send destinations", prefix: "action." },
  { label: "Approvals", prefix: "approval." },
  { label: "Groups and access", prefix: "user_group." },
];
const OUTCOME_STYLE: Record<Row["outcome"], string> = {
  success: "text-text-03",
  failure: "text-status-error-05",
  denied: "text-status-warning-05",
};

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 shadow-sm";
const field = "min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";

/**
 * The audit trail: who did what, and what the system refused. Records hold
 * counts, names and fingerprints, never task text, draft text or document text.
 */
export default function AuditLogPage() {
  const [prefix, setPrefix] = useState("");
  const [outcome, setOutcome] = useState("");
  const [actor, setActor] = useState("");

  const qs = (before: number | null) => {
    const p = new URLSearchParams({ limit: "50" });
    if (before) p.set("before_id", String(before));
    if (prefix) p.set("action_prefix", prefix);
    if (outcome) p.set("outcome", outcome);
    if (actor.trim()) p.set("actor", actor.trim());
    return `/api/admin/audit?${p.toString()}`;
  };
  const { data, error, isLoading, size, setSize, isValidating } = useSWRInfinite<Page>(
    (index, prev) => (index === 0 ? qs(null) : prev?.next_before_id ? qs(prev.next_before_id) : null),
    errorHandlingFetcher
  );
  const rows = (data ?? []).flatMap((p) => p.events);
  const hasMore = !!data && !!data[data.length - 1]?.next_before_id;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 sm:p-8" data-testid="audit-log-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-text-05">Audit log</h1>
        <p className="text-sm text-text-03">
          Who did what, and what was refused. Records never hold task, draft or document text.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          Area
          <select className={field} value={prefix} onChange={(e) => { setPrefix(e.target.value); setSize(1); }}>
            {AREAS.map((a) => (
              <option key={a.label} value={a.prefix}>{a.label}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          Outcome
          <select className={field} value={outcome} onChange={(e) => { setOutcome(e.target.value); setSize(1); }}>
            <option value="">All</option>
            <option value="success">Succeeded</option>
            <option value="failure">Failed</option>
            <option value="denied">Refused</option>
          </select>
        </label>
        <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-text-05">
          Person
          <input className={`${field} w-full`} placeholder="Part of an email address" value={actor} onChange={(e) => { setActor(e.target.value); setSize(1); }} />
        </label>
      </div>

      {isLoading ? (
        <p className="text-sm text-text-03">Loading…</p>
      ) : error ? (
        <p role="alert" className="text-sm text-text-05">The audit log could not be loaded.</p>
      ) : rows.length === 0 ? (
        <section className={`${card} p-5`}>
          <p className="text-sm text-text-03">Nothing matches these filters.</p>
        </section>
      ) : (
        <ul className={`${card} overflow-hidden`} data-testid="audit-list">
          {rows.map((r) => (
            <li key={r.id} className="border-t border-border-01 px-4 py-3 first:border-t-0" data-testid="audit-row">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-xs text-text-03">{new Date(r.created_at).toLocaleString()}</span>
                <span className="text-xs font-medium text-text-05">{r.action}</span>
                <span className={`text-xs font-semibold ${OUTCOME_STYLE[r.outcome]}`}>
                  {r.outcome === "denied" ? "refused" : r.outcome}
                </span>
                <span className="text-xs text-text-03">{r.actor_email ?? "system"}</span>
              </div>
              <p className="mt-1 text-sm text-text-05">{r.summary}</p>
              {r.details && Object.keys(r.details).length > 0 && (
                <details className="mt-1 text-xs text-text-03">
                  <summary className="cursor-pointer">Details</summary>
                  <pre className="mt-1 overflow-auto whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1">{JSON.stringify(r.details, null, 2)}</pre>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div>
          <button
            type="button"
            className="min-h-11 rounded-xl border border-border-02 px-5 text-sm font-semibold text-text-05 disabled:opacity-50"
            disabled={isValidating}
            onClick={() => setSize(size + 1)}
          >
            {isValidating ? "Loading…" : "Show older events"}
          </button>
        </div>
      )}
    </div>
  );
}
