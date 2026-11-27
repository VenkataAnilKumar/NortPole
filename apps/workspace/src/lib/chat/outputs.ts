import type { Slide } from "@/lib/chat/presentation";
import { sheetToCsv } from "@/lib/chat/spreadsheet";

export type OutputArtifact =
  | { kind: "document"; payload: { body: string } }
  | { kind: "presentation"; payload: { slides: Slide[] } }
  | { kind: "spreadsheet"; payload: { rows: string[][] } };

export interface OutputSummary {
  id: string;
  name: string;
  kind: OutputArtifact["kind"];
  version: number;
  updated_at: string;
}

export type OutputDetail = OutputSummary & { artifact: OutputArtifact };
export type OutputLocation = OutputSummary & { projectId: number };
export type SavedOutput = OutputDetail & OutputLocation;

export const projectOutputsKey = (projectId: number) => `/api/user/projects/${projectId}/outputs`;
export const outputDestinationsKey = "/api/manage/document-set/output-destinations";

export function outputFileName(name: string, fallback: string) {
  return (
    name
      .replace(/[<>:"/\\|?*]/g, "_")
      .split("")
      .map((character) => character.charCodeAt(0) < 32 ? "_" : character)
      .join("")
      .trim()
      .replace(/[. ]+$/, "") || fallback
  );
}

export function knowledgeSnapshot(artifact: OutputArtifact) {
  switch (artifact.kind) {
    case "document":
      return { format: "md", text: artifact.payload.body };
    case "spreadsheet":
      return { format: "csv", text: sheetToCsv(artifact.payload.rows) };
    case "presentation":
      return {
        format: "md",
        text: artifact.payload.slides
          .map(({ title, text, kind, image }) =>
            [
              `## ${title}`,
              kind === "points"
                ? text
                    .split("\n")
                    .filter(Boolean)
                    .map((point) => `- ${point}`)
                    .join("\n")
                : text,
              image?.name,
            ]
              .filter(Boolean)
              .join("\n\n"),
          )
          .join("\n\n"),
      };
  }
}
