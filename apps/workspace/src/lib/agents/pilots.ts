import type { MinimalAgent } from "./types";

export const AGENT_PILOTS = {
  research: {
    requiresKnowledge: true,
    name: "Research",
    description: "Write a cited briefing using permissioned Knowledge.",
    instructions:
      "Write a concise briefing with a summary, key findings, and open questions. Cite the Knowledge excerpts that support the findings. Say when the evidence is incomplete.",
    starters: ["Write a briefing on the key findings and open questions in this Knowledge library."],
  },
  "document-analysis": {
    requiresKnowledge: true,
    name: "Document Analysis",
    description: "Compare or summarize selected Knowledge passages with citations.",
    instructions:
      "Analyze only the supplied passages. Compare agreements, differences, and missing evidence. Attribute each finding to the document that supports it.",
    starters: [
      "Compare these documents. Summarize where they agree, where they differ, and what remains unclear.",
    ],
  },
  reporting: {
    requiresKnowledge: true,
    name: "Reporting",
    description: "Write a cited status report for a chosen period using selected Knowledge.",
    instructions:
      "Write a clear status report with progress, metrics, blockers, next steps, and evidence gaps. Cite the supplied Knowledge and flag details the evidence cannot confirm.",
    starters: [
      "Write a status report highlighting progress, metrics, blockers, and next steps.",
      "Summarize support volume, recurring issues, and unresolved escalations for the selected period.",
      "Summarize budget variances for the selected period and distinguish confirmed causes from open questions.",
    ],
  },
  "spreadsheet-analysis": {
    requiresKnowledge: false,
    name: "Spreadsheet Analysis",
    description: "Check totals, missing data, duplicate rows, and unusual values in an uploaded spreadsheet.",
    instructions: "Analyze the uploaded spreadsheet and show the calculations and row references in the report.",
    starters: ["Analyze this spreadsheet."],
  },
  "meeting-recap": {
    requiresKnowledge: false,
    name: "Meeting Recap",
    description: "Pull decisions, action items, and open questions from meeting notes.",
    instructions: "Extract decisions, action items, and open questions from the notes. Use quoted evidence and include owners and due dates when stated.",
    starters: [],
  },
} as const;

export type AgentPilotKind = keyof typeof AGENT_PILOTS;

export type AgentInputType = "knowledge" | "spreadsheet" | "meetingNotes";

const pilotInputTypes = {
  research: "knowledge",
  "document-analysis": "knowledge",
  reporting: "knowledge",
  "spreadsheet-analysis": "spreadsheet",
  "meeting-recap": "meetingNotes",
} satisfies Record<AgentPilotKind, AgentInputType>;

export function getAgentInputType(
  agent: MinimalAgent
): AgentInputType | undefined {
  if (agent.active_pilot) return pilotInputTypes[agent.active_pilot];
  if (
    agent.document_sets?.length ||
    agent.attached_document_count ||
    agent.hierarchy_node_count
  ) {
    return "knowledge";
  }
}

export interface AgentPilotInput {
  kind: AgentPilotKind;
  libraries: { id: number; name: string }[];
}
