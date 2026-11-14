import type { SearchFullResponse } from "@/lib/search/types";

/**
 * Community build: document search through the enterprise search endpoint is
 * not available, so this returns no results. NortPole replaces it with its own
 * search service.
 */
export async function searchDocuments(
  _query: string,
  _options?: unknown
): Promise<SearchFullResponse> {
  return { search_docs: [] } as unknown as SearchFullResponse;
}
