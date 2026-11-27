import type { MinimalAgent } from "./types";

const fillerWords = new Set([
  "a",
  "an",
  "and",
  "can",
  "for",
  "in",
  "me",
  "my",
  "of",
  "on",
  "please",
  "the",
  "to",
  "with",
  "you",
]);

function normalize(text: string): string {
  return text.normalize("NFKC").toLowerCase();
}

function words(text: string): string[] {
  return text.match(/[\p{L}\p{M}\p{N}]+/gu) ?? [];
}

export function createAgentCatalogMatcher(query: string) {
  const phrase = normalize(query.trim());
  if (!phrase) return () => true;

  const terms = words(phrase).filter((word) => !fillerWords.has(word));

  return (agent: MinimalAgent) => {
    const fields = [
      agent.name,
      agent.description,
      ...(agent.labels ?? []).map((label) => label.name),
    ].map(normalize);

    if (fields.some((field) => field.includes(phrase))) return true;
    if (terms.length === 0) return false;

    const searchableWords = fields.flatMap(words);
    return terms.every((term) => searchableWords.some((word) => word.startsWith(term)));
  };
}
