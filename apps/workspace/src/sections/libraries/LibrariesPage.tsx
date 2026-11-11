"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";

interface DocumentSetSummary {
  id: number;
  name: string;
  description: string | null;
  is_up_to_date: boolean;
  is_public: boolean;
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";

/**
 * Libraries: approved collections of sources an agent may read. Today this lists
 * the document sets the backend already has. Connecting sources, permission
 * sync and freshness checks arrive with the knowledge phase (A5); until a
 * retrieval index is enabled this page is honest about being empty.
 */
export default function LibrariesPage() {
  const { data, error, isLoading } = useSWR<DocumentSetSummary[]>(
    SWR_KEYS.documentSets,
    errorHandlingFetcher
  );
  const libraries = data ?? [];

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-8" data-testid="libraries-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Libraries</h1>
        <p className="text-sm text-text-03">
          Approved collections of sources that agents may read for you. Agents only see what your own access allows.
        </p>
      </header>

      <div role="tablist" aria-label="Library views" className="flex gap-1 border-b border-border-01">
        {["Shared", "Team", "Status"].map((t, i) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={i === 0}
            aria-disabled={i !== 0}
            disabled={i !== 0}
            className={`min-h-11 px-4 text-sm font-semibold ${i === 0 ? "border-b-2 border-text-05 text-text-05" : "cursor-not-allowed text-text-03 opacity-60"}`}
            title={i === 0 ? undefined : "Available when sources can be connected"}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-text-03">Loading libraries…</p>
      ) : error ? (
        <div className={card} role="alert">
          <p className="text-sm text-text-05">Libraries could not be loaded. Try again in a moment.</p>
        </div>
      ) : libraries.length === 0 ? (
        <section className={card} aria-labelledby="lib-empty">
          <h2 id="lib-empty" className="mb-1 text-base font-semibold text-text-05">No libraries yet</h2>
          <p className="mb-3 text-sm text-text-03">
            A library appears here once an administrator connects a source and approves it. Nothing is shared
            until then.
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-text-03">
            <li>Each library shows its indexing status, freshness and any conflicting versions.</li>
            <li>Citations from a library always link to a passage you are allowed to open.</li>
            <li>If your access to a source is removed, answers that depend on it are withheld.</li>
          </ul>
          <p className="mt-4 text-xs text-text-03">
            This build runs without a retrieval index, so sources cannot be connected yet.
          </p>
        </section>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {libraries.map((l) => (
            <li key={l.id} className={card}>
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-semibold text-text-05">{l.name}</h2>
                <span
                  className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${l.is_up_to_date ? "bg-status-success-01 text-status-success-05" : "bg-status-warning-01 text-status-warning-05"}`}
                >
                  {l.is_up_to_date ? "Up to date" : "Syncing"}
                </span>
              </div>
              {l.description && <p className="mt-2 text-sm text-text-03">{l.description}</p>}
              <p className="mt-3 text-xs text-text-03">{l.is_public ? "Shared with everyone" : "Limited to selected people"}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
