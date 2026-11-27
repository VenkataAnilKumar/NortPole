"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type { ComposerSelection } from "@/app/app/types";
import { MAX_SEARCH_RESULTS, openChatWithSearchEvidence } from "@/lib/chat/searchHandoff";
import { useUser } from "@/providers/UserProvider";
import ChatSearchCommandMenu from "@/sections/sidebar/ChatSearchCommandMenu";

type SearchTab = "knowledge" | "chats" | "workflows";

interface SearchFilters {
  library_id: number | null;
  source: string | null;
  updated_since: string | null;
  status: string | null;
}

interface SearchResult {
  id: string;
  chunk_id?: number;
  title: string;
  source: string;
  status?: string | null;
  excerpt: string;
  updated_at: string | null;
  url: string | null;
}

interface SearchResponse {
  results: SearchResult[];
  next_cursor: string | null;
  limited: boolean;
  lexical_only: boolean;
}

const URL = "/api/search/workspace";
const TABS: { id: SearchTab; label: string }[] = [
  { id: "knowledge", label: "Knowledge" },
  { id: "chats", label: "Chats" },
  { id: "workflows", label: "Workflows" },
];
const KNOWLEDGE_SOURCES: Record<string, string> = {
  file: "Uploaded library files",
  ingestion_api: "Indexed library documents",
  user_file: "My files",
  google_drive: "Google Drive",
};
const WORKFLOW_SOURCES: Record<string, string> = {
  schedule: "Schedule",
  scheduled_run: "Scheduled run",
  expense_review: "Expense review",
  document_review: "Document review",
};
const WORKFLOW_STATUS: Record<string, string> = {
  active: "Active",
  paused: "Paused",
  ended: "Finished",
  complete: "Complete",
  review_complete: "Review complete",
  needs_review: "Needs review",
  plan_ready: "Plan ready",
  plan_failed: "Plan failed",
  failed: "Failed",
  stopped: "Stopped",
  skipped: "Skipped",
  drive_skipped: "Drive input skipped",
};
const button = "inline-flex min-h-10 items-center justify-center rounded-lg border border-border-02 px-3 text-sm font-medium text-text-05 focus-visible:outline focus-visible:outline-2 disabled:opacity-50";
const field = "min-h-10 w-full rounded-lg border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05 focus-visible:outline focus-visible:outline-2";
const emptyFilters: SearchFilters = { library_id: null, source: null, updated_since: null, status: null };

export default function WorkspaceSearchPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { user } = useUser();
  const [selected, setSelected] = useState<ComposerSelection[]>([]);
  const [handoffError, setHandoffError] = useState(false);
  const [tab, setTab] = useState<SearchTab>("knowledge");
  const { data: libraries, error: libraryError, mutate: retryLibraries } = useSWR<{ id: number; name: string; drive_search?: boolean }[]>(
    tab === "knowledge" ? `${URL}/libraries` : null, errorHandlingFetcher
  );
  const [query, setQuery] = useState("");
  const [tabFilters, setTabFilters] = useState<Record<SearchTab, SearchFilters>>({
    knowledge: emptyFilters, chats: emptyFilters, workflows: emptyFilters,
  });
  const filters = tabFilters[tab];
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const request = useRef<AbortController | null>(null);
  const lastSearch = useRef<{ query: string; filters: SearchFilters; tab: SearchTab } | null>(null);
  const retryPage = useRef<string | null>(null);
  const resultsRegion = useRef<HTMLDivElement>(null);
  const openedSource = useRef(false);
  const loadedCount = useRef(0);

  const search = useCallback(async (
    text: string,
    scope: SearchFilters,
    section: SearchTab,
    cursor: string | null = null,
    pageSize = 20
  ) => {
    request.current?.abort();
    const nextRequest = new AbortController();
    request.current = nextRequest;
    lastSearch.current = { query: text, filters: scope, tab: section };
    retryPage.current = cursor;
    setLoading(true);
    setError(null);
    setExpired(false);
    if (!cursor) {
      loadedCount.current = 0;
      setResponse(null);
    }
    try {
      const result = await fetch(section === "knowledge" ? URL : `${URL}/activity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, ...scope, tab: section, cursor, page_size: pageSize }),
        signal: nextRequest.signal,
        cache: "no-store",
      });
      if (nextRequest.signal.aborted) return;
      if (result.status === 410) {
        setExpired(true);
        setError("These results expired. Run the search again.");
        return;
      }
      if (!result.ok) throw new Error("Search request failed");
      const next: SearchResponse = await result.json();
      if (nextRequest.signal.aborted) return;
      loadedCount.current += next.results.length;
      setResponse((previous) => ({
        ...next,
        results: cursor && previous ? [...previous.results, ...next.results] : next.results,
      }));
    } catch {
      if (!nextRequest.signal.aborted) setError("Search could not be completed. Try again.");
    } finally {
      if (!nextRequest.signal.aborted) {
        if (resultsRegion.current) resultsRegion.current.hidden = false;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const restore = () => {
      const last = lastSearch.current;
      if (last) void search(last.query, last.filters, last.tab, null, Math.max(20, loadedCount.current));
    };
    const hide = () => {
      if (resultsRegion.current) resultsRegion.current.hidden = true;
    };
    // A restored browser snapshot must reauthorize excerpts before displaying them.
    const pageShow = (event: PageTransitionEvent) => {
      if (event.persisted) restore();
    };
    const onFocus = () => {
      if (openedSource.current) {
        openedSource.current = false;
        restore();
      }
    };
    window.addEventListener("focus", onFocus);
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", pageShow);
    return () => {
      request.current?.abort();
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", pageShow);
    };
  }, [search]);

  function updateFilters(next: SearchFilters) {
    setTabFilters((current) => ({ ...current, [tab]: next }));
    const last = lastSearch.current;
    if (last?.tab === tab) void search(last.query, next, tab);
  }

  function selectTab(next: SearchTab) {
    if (next === tab) return;
    setTab(next);
    const text = query.trim();
    if (text) void search(text, tabFilters[next], next);
    else {
      request.current?.abort();
      lastSearch.current = null;
      loadedCount.current = 0;
      setResponse(null);
      setLoading(false);
      setError(null);
      setExpired(false);
    }
  }

  const selectedLibrary = libraries?.find((library) => library.id === filters.library_id);
  function askInChat(items: ComposerSelection[]) {
    if (!user?.id) return;
    try {
      openChatWithSearchEvidence(String(user.id), items);
    } catch {
      setHandoffError(true);
    }
  }

  const sources = tab === "knowledge" ? KNOWLEDGE_SOURCES : WORKFLOW_SOURCES;
  const activeLabel = TABS.find((item) => item.id === tab)?.label ?? "Knowledge";

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-6 sm:px-8 sm:py-10" data-testid="workspace-search">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">{workspaceText("search")}</h1>
        <ChatSearchCommandMenu trigger={(open) => (
          <ActionButton type="button" onClick={open} className={button}>{workspaceText("quickFind")}</ActionButton>
        )} />
      </header>

      <form className="flex gap-2" role="search" onSubmit={(event) => {
        event.preventDefault();
        if (query.trim()) void search(query.trim(), filters, tab);
      }}>
        <NativeInput type="search" aria-label={`Search ${activeLabel}`} maxLength={2048} value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder={tab === "knowledge" ? "Search files and libraries" : tab === "chats" ? "Search chat titles and messages" : "Search workflows and run results"} className={field} />
        <ActionButton type="submit" className={`${button} min-w-[5rem] bg-text-05 text-background-neutral-00`} disabled={!query.trim()}>{workspaceText("search")}</ActionButton>
      </form>

      <ResponsiveLayout display="flex" role="tablist" aria-label={workspaceText("searchScope")} className="gap-1 border-b border-border-01">
        {TABS.map((item, index) => (
          <ActionButton
            type="button"
            id={`search-tab-${item.id}`}
            key={item.id}
            role="tab"
            aria-selected={item.id === tab}
            tabIndex={item.id === tab ? 0 : -1}
            aria-controls="workspace-search-results"
            className={`min-h-11 px-3 text-sm font-semibold ${tab === item.id ? "border-b-2 border-text-05 text-text-05" : "text-text-03"}`}
            onClick={() => selectTab(item.id)}
            onKeyDown={(event) => {
              const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
              if (!offset && event.key !== "Home" && event.key !== "End") return;
              event.preventDefault();
              const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : (index + offset + TABS.length) % TABS.length;
              const next = TABS[nextIndex]!.id;
              selectTab(next);
              document.getElementById(`search-tab-${next}`)?.focus();
            }}
          >{item.label}</ActionButton>
        ))}
      </ResponsiveLayout>

      <section role="tabpanel" id="workspace-search-results" aria-labelledby={`search-tab-${tab}`} className="flex flex-col gap-4">
        <ResponsiveLayout display="grid" className="gap-3 sm:grid-cols-3">
          {tab === "knowledge" && (
          <label className="flex flex-col gap-1 text-sm text-text-03">{workspaceText("library")}<NativeSelect className={field} value={filters.library_id ?? ""} disabled={!libraries} onChange={(event) => {
              const libraryId = event.target.value ? Number(event.target.value) : null;
              const driveSearch = libraries?.find((library) => library.id === libraryId)?.drive_search;
              updateFilters({
                ...filters,
                library_id: libraryId,
                source: filters.source === "google_drive" && !driveSearch ? null : filters.source,
              });
            }}>
              <option value="">{workspaceText("allAccessibleLibraries")}</option>
              {libraries?.map((library) => <option key={library.id} value={library.id}>{library.name}</option>)}
            </NativeSelect>
          </label>)}
          {tab !== "chats" && <label className="flex flex-col gap-1 text-sm text-text-03">
            {tab === "knowledge" ? "Source" : "Workflow type"}
            <NativeSelect className={field} value={filters.source ?? ""} onChange={(event) =>
              updateFilters({ ...filters, source: event.target.value || null })
            }>
              <option value="">{tab === "knowledge" ? "All sources" : "All workflow types"}</option>
              {Object.entries(sources).filter(([id]) =>
                id !== "google_drive" || selectedLibrary?.drive_search
              ).map(([id, label]) => <option value={id} key={id}>{label}</option>)}
            </NativeSelect>
          </label>}
          {tab === "workflows" && <label className="flex flex-col gap-1 text-sm text-text-03">{workspaceText("status")}<NativeSelect className={field} value={filters.status ?? ""} onChange={(event) =>
              updateFilters({ ...filters, status: event.target.value || null })
            }>
              <option value="">{workspaceText("anyStatus")}</option>
              {Object.entries(WORKFLOW_STATUS).map(([id, label]) => <option value={id} key={id}>{label}</option>)}
            </NativeSelect>
          </label>}
          <label className="flex flex-col gap-1 text-sm text-text-03">
            {tab === "workflows" ? "Run or update date since" : "Updated since"}
            <NativeInput type="date" className={field} value={filters.updated_since?.slice(0, 10) ?? ""} onChange={(event) =>
              updateFilters({ ...filters, updated_since: event.target.value ? `${event.target.value}T00:00:00Z` : null })
            } />
          </label>
        </ResponsiveLayout>
        {tab === "knowledge" && libraryError && <ResponsiveLayout display="flex" className="items-center gap-3 text-sm text-text-03">
          <span>{workspaceText("libraryFiltersCouldNotBeLoaded")}</span>
          <ActionButton type="button" className={button} onClick={() => void retryLibraries()}>{workspaceText("retryLibraries")}</ActionButton>
        </ResponsiveLayout>}
        {Object.values(filters).some((value) => value !== null) && (
          <ActionButton type="button" className={`${button} self-start`} onClick={() => updateFilters(emptyFilters)}>{workspaceText("clearFilters")}</ActionButton>
        )}

        {tab === "knowledge" && (selected.length > 0 || selectedLibrary) && (
          <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2 rounded-xl border border-border-01 p-3">
            {selected.map((item) => (
              <ActionButton key={item.id} type="button" className={button}
                aria-label={`Remove ${item.label}`}
                onClick={() => setSelected((items) => items.filter((selection) => selection.id !== item.id))}>
                {item.label} ×
              </ActionButton>
            ))}
            {selected.length > 0 && (
              <ActionButton type="button" className={button} onClick={() => askInChat(selected)} disabled={!user?.id}>{workspaceText("askInChat")}</ActionButton>
            )}
            {selectedLibrary && selected.length === 0 && (
              <ActionButton type="button" className={button} disabled={!user?.id}
                onClick={() => askInChat([{ kind: "search-library", id: String(selectedLibrary.id), label: selectedLibrary.name }])}>{workspaceText("askAboutThisLibrary")}</ActionButton>
            )}
            {handoffError && <p role="alert" className="text-sm text-text-03">{workspaceText("chatCouldNotBeOpenedTryAgain")}</p>}
          </ResponsiveLayout>
        )}

        <div ref={resultsRegion} aria-busy={loading}>
          <div role="status" className="mb-3 text-sm text-text-03">
            {loading ? `Searching ${activeLabel}…` : response && !error ? `${response.results.length} results` : ""}
          </div>
          {error && <ResponsiveLayout display="flex" role="alert" className="mb-3 flex-wrap items-center gap-3 text-sm text-text-05">
            <p>{error}</p>
            <ActionButton type="button" className={button} onClick={() => {
              const last = lastSearch.current;
              if (last) void search(last.query, last.filters, last.tab, expired ? null : retryPage.current);
            }}>{expired ? "Search again" : "Retry search"}</ActionButton>
          </ResponsiveLayout>}
          {response?.lexical_only && <p className="mb-3 text-sm text-text-03">{workspaceText("showingKeywordMatchesSemanticSearchIsTemporarilyUnavailable")}</p>}
          {response?.results.length === 0 && !loading && !error && (
            <p className="rounded-xl border border-border-01 p-5 text-sm text-text-03">{workspaceText("noMatchingResultsTryAnotherQueryOrClearA")}</p>
          )}
          {!!response?.results.length && (
            <ul className="divide-y divide-border-01 overflow-hidden rounded-xl border border-border-01">
              {response.results.map((result) => (
                <li key={result.id} className="flex flex-col gap-2 p-4 sm:p-5">
                  <p className="text-xs text-text-03">
                    {KNOWLEDGE_SOURCES[result.source] ?? WORKFLOW_SOURCES[result.source] ?? (result.source === "chat" ? "Chat" : result.source)}
                    {result.status && ` · ${WORKFLOW_STATUS[result.status] ?? result.status}`}
                    {result.updated_at && ` · Updated ${new Date(result.updated_at).toLocaleDateString()}`}
                  </p>
                  <h3 className="break-words text-base font-semibold text-text-05">
                    {result.url ? <a className="hover:underline focus-visible:underline" href={result.url} target="_blank" rel="noopener noreferrer" onClick={() => {
                      // Keep the search available in this tab while opening the original.
                      openedSource.current = true;
                    }}>{result.title}</a> : result.title}
                  </h3>
                  {result.excerpt && <p className="break-words text-sm leading-relaxed text-text-03">{result.excerpt}</p>}
                  {tab === "knowledge" && result.chunk_id !== undefined && (
                    <label className="flex min-h-9 items-center gap-2 self-start text-sm text-text-03">
                      <NativeInput type="checkbox" aria-label={`Select ${result.title} for Chat`}
                        checked={selected.some((item) => item.id === result.id)}
                        disabled={selected.length >= MAX_SEARCH_RESULTS && !selected.some((item) => item.id === result.id)}
                        onChange={(event) => {
                          const checked = event.target.checked;
                          setSelected((items) => checked
                            ? [...items, { kind: "search-result", id: result.id, chunkId: result.chunk_id, label: result.title }]
                            : items.filter((item) => item.id !== result.id)
                          );
                        }} />{workspaceText("useInChat")}</label>
                  )}
                </li>
              ))}
            </ul>
          )}
          {response?.limited && <p className="mt-3 text-sm text-text-03">{workspaceText("showingTheHighestRankedMatchesRefineYourQueryTo")}</p>}
          {response?.next_cursor && !expired && (
            <ActionButton type="button" className={`${button} mt-4`} disabled={loading} onClick={() => {
              const last = lastSearch.current;
              if (last) void search(last.query, last.filters, last.tab, response.next_cursor);
            }}>{workspaceText("moreResults")}</ActionButton>
          )}
        </div>
      </section>
    </main>
  );
}
