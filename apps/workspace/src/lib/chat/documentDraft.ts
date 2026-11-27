import type { CitationMap } from "@/app/app/types";
import type { NortPoleDocument } from "@/lib/search/types";

export const MAX_DOCUMENT_LENGTH = 100_000;

export function documentLink(value: string): string | null {
  try {
    const parsed = new URL(value);
    return ["https:", "http:", "mailto:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

export function draftFromResponse(
  answer: string,
  citations: CitationMap,
  documents: NortPoleDocument[],
  sourcesHeading: string,
) {
  const sources = Object.entries(citations).flatMap(([number, id]) => {
    const source = documents.find((document) => document.document_id === id);
    if (!source) return [];
    const label = (source.semantic_identifier || source.link || id)
      .replace(/[\\[\]*_`<>]/g, "\\$&")
      .replace(/\s+/g, " ")
      .trim();
    const url = documentLink(source.link);
    return [`- ${number}. ${url ? `[${label}](<${url.replaceAll(">", "%3E")}>)` : label}`];
  });
  return sources.length
    ? `${answer.trimEnd()}\n\n## ${sourcesHeading}\n\n${sources.join("\n")}`
    : answer;
}
