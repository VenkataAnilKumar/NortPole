import { loadPage, clearQueryParameter } from "@opal/navigation";
import type { ComposerSelection } from "@/app/app/types";

export const MAX_SEARCH_RESULTS = 5;
const STORAGE_KEY = "nortpole-search-handoff";
const MAX_AGE_MS = 120_000;

export function openChatWithSearchEvidence(userId: string, selections: ComposerSelection[]) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ userId, selections, createdAt: Date.now() }));
  loadPage("/app?fromSearch=1");
}

export function takeSearchEvidence(userId: string): ComposerSelection[] {
  const url = new URL(window.location.href);
  if (url.searchParams.get("fromSearch") !== "1") return [];
  clearQueryParameter("fromSearch");
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    if (!saved) return [];
    const { userId: owner, createdAt, selections } = JSON.parse(saved);
    if (owner !== userId || typeof createdAt !== "number" ||
        Date.now() - createdAt > MAX_AGE_MS || !Array.isArray(selections)) return [];
    return selections.slice(0, MAX_SEARCH_RESULTS).filter((item) =>
      item && typeof item.id === "string" && typeof item.label === "string" &&
      ((item.kind === "search-result" && Number.isSafeInteger(item.chunkId) && item.chunkId >= 0) ||
       (item.kind === "search-library" && /^[1-9]\d*$/.test(item.id)))
    );
  } catch {
    return [];
  }
}
