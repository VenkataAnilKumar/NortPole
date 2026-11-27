import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useId, useState } from "react";
import { Button } from "@opal/components";
import type { ComposerSelection } from "@/app/app/types";
import type { AgentPilotInput } from "@/lib/agents/pilots";
import { MAX_SEARCH_RESULTS } from "@/lib/chat/searchHandoff";

interface SearchHit {
  id: string;
  chunk_id: number;
  title: string;
  excerpt: string;
}

export function PilotDocumentPicker({
  libraries,
  selected,
  onToggle,
  disabled,
}: {
  libraries: AgentPilotInput["libraries"];
  selected: ComposerSelection[];
  onToggle: (item: ComposerSelection) => void;
  disabled: boolean;
}) {
  const hitPrefix = useId();
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [libraryId, setLibraryId] = useState<number | undefined>();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const library = libraries.find((item) => item.id === libraryId) ?? libraries[0];

  async function search() {
    if (!library || !query.trim() || loading || disabled) return;
    setLoading(true);
    setFailed(false);
    setHits(null);
    try {
      const response = await fetch("/api/search/workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), library_id: library.id, page_size: 10 }),
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Search failed");
      setHits((await response.json()).results);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <details className="rounded-lg border border-border-01 px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium text-text-05">{workspaceText("selectDocuments")}{" "}{selected.length > 0 && `(${selected.length})`}
      </summary>
      {!library ? (
        <p className="mt-2 text-text-03">{workspaceText("youHaveNoAccessibleKnowledgeLibrariesForThisAgent")}</p>
      ) : (
        <ResponsiveLayout display="flex" className="mt-2 flex-col gap-2">
          <label className="flex flex-col gap-1">{workspaceText("knowledgeLibrary")}<NativeSelect
              value={library.id}
              disabled={disabled || loading}
              onChange={(event) => {
                setLibraryId(Number(event.target.value));
                setHits(null);
                setFailed(false);
              }}
              className="rounded-md border border-border-01 bg-background-neutral-00 p-2"
            >
              {libraries.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </NativeSelect>
          </label>
          <ResponsiveLayout display="flex" className="gap-2">
            <NativeInput
              type="search"
              value={query}
              aria-label={workspaceText("searchLibraryDocuments")}
              placeholder={workspaceText("searchDocuments")}
              maxLength={2048}
              className="min-w-0 flex-1 rounded-md border border-border-01 bg-background-neutral-00 p-2"
              disabled={disabled || loading}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                event.stopPropagation();
                void search();
              }}
            />
            <Button
              type="button"
              size="sm"
              prominence="secondary"
              onClick={() => void search()}
              disabled={disabled || loading || !query.trim()}
            >{workspaceText("search")}</Button>
          </ResponsiveLayout>
          {loading && <p role="status">{workspaceText("searchingKnowledge")}</p>}
          {failed && <p role="alert">{workspaceText("couldNotSearchThisLibraryTryAgain")}</p>}
          {hits?.length === 0 && <p role="status">{workspaceText("noMatchingPassages")}</p>}
          {!!hits?.length && (
            <ul className="max-h-48 overflow-auto">
              {hits.map((hit) => {
                const checked = selected.some((item) => item.id === hit.id);
                const hitId = hitPrefix + hit.id;
                return (
                  <li key={hit.id}>
                    <ResponsiveLayout display="flex" className="items-start gap-2 border-t border-border-01 py-2">
                      <NativeInput
                        id={hitId}
                        aria-describedby={hitId + "-excerpt"}
                        type="checkbox"
                        checked={checked}
                        disabled={disabled || (!checked && selected.length >= MAX_SEARCH_RESULTS)}
                        onChange={() =>
                          onToggle({
                            kind: "search-result",
                            id: hit.id,
                            chunkId: hit.chunk_id,
                            label: hit.title,
                          })
                        }
                      />
                      <span>
                        <label htmlFor={hitId} className="block cursor-pointer font-medium">{hit.title}</label>
                        <span id={hitId + "-excerpt"} className="block text-text-03">{hit.excerpt}</span>
                      </span>
                    </ResponsiveLayout>
                  </li>
                );
              })}
            </ul>
          )}
        </ResponsiveLayout>
      )}
    </details>
  );
}
