export const MAX_NOTES_LENGTH = 6000;
export const MAX_SLIDES = 24;
export const MAX_POINTS = 5;

export type SlideKind = "title" | "points" | "chart";

export interface ChartImage {
  data: string;
  name: string;
  width: number;
  height: number;
}

export interface Slide {
  kind: SlideKind;
  title: string;
  text: string;
  image?: ChartImage;
}

export function slidePoints(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitPoint(text: string): string[] {
  const segments: string[] = [];
  let remaining = text;
  while (remaining.length > 120) {
    const space = remaining.lastIndexOf(" ", 120);
    const end = space > 0 ? space : 120;
    segments.push(remaining.slice(0, end));
    remaining = remaining.slice(end).trimStart();
  }
  if (remaining) segments.push(remaining);
  return segments;
}

/** Turn headings and lines into an editable deck, preserving note order and wording. */
export function deckFromNotes(
  notes: string,
  labels: { title: string; points: string },
): Slide[] | null {
  if (notes.length > MAX_NOTES_LENGTH) return null;
  const lines = slidePoints(notes);
  if (!lines.length) return null;

  const first = lines[0]!;
  const explicitTitle = /^#\s+(.*)$/.exec(first)?.[1];
  const plainTitle =
    first.length <= 80 &&
    !/^([-*+]\s|\d+\.\s|#)/.test(first) &&
    (lines.length === 1 || notes.trim().startsWith(first + "\n\n"));
  const title = explicitTitle ?? (plainTitle ? first : labels.title);
  const slides: Slide[] = [{ kind: "title", title: title.slice(0, 80), text: "" }];
  let heading = labels.points;
  let points: string[] = [];
  const flush = () => {
    for (let index = 0; index < points.length; index += MAX_POINTS) {
      slides.push({
        kind: "points",
        title: heading,
        text: points.slice(index, index + MAX_POINTS).join("\n"),
      });
    }
    points = [];
  };
  if (title.length > 80) points.push(...splitPoint(title.slice(80).trimStart()));
  for (const line of lines.slice(explicitTitle || plainTitle ? 1 : 0)) {
    const section = /^#{1,6}\s+(.*)$/.exec(line)?.[1];
    if (section) {
      flush();
      heading = section.slice(0, 80);
      if (section.length > 80) points.push(...splitPoint(section.slice(80).trimStart()));
    } else {
      const point = line.replace(/^(?:[-*+]\s+|\d+[.)]\s+)/, "").trim();
      if (point) points.push(...splitPoint(point));
    }
  }
  flush();
  return slides.length > MAX_SLIDES ? null : slides;
}
