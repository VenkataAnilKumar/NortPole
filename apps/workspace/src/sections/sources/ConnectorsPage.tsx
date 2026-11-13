"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card, h1Class, pageClass, titleCase } from "@/sections/sources/shared";

/**
 * Connectors: the outside systems whose documents are in the workspace's search. People see which systems are
 * connected, not their settings; administrators connect them. Answers only use documents the person can open.
 */
export default function ConnectorsPage() {
  const { data, error, isLoading } = useSWR<{ sources: string[] }>("/api/manage/indexed-sources", errorHandlingFetcher);
  const sources = (data?.sources ?? []).filter((s) => s !== "ingestion_api" && s !== "user_file");

  return (
    <div className={pageClass} data-testid="connectors-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>Connectors</h1>
        <p className="text-sm text-text-03">
          Systems connected to this workspace. Assistants read from them only what your own access in that system allows. Administrators add and manage connectors.
        </p>
      </header>
      {isLoading && <p className="text-sm text-text-03">Loading connectors…</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">Connectors could not be loaded. Try again in a moment.</p>}
      {data && sources.length === 0 && (
        <section className={card}>
          <h2 className="text-base font-semibold text-text-05">No systems connected yet</h2>
          <p className="mt-1 text-sm text-text-03">A connected system, such as a shared drive, appears here once an administrator connects it and its first sync finishes.</p>
        </section>
      )}
      {sources.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {sources.map((s) => (
            <li key={s} className={card} data-testid="connector-source">
              <h2 className="text-base font-semibold text-text-05">{titleCase(s)}</h2>
              <p className="mt-1 text-sm text-text-03">Connected. Its documents are in search.</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
