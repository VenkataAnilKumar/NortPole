"use client";

import { useTranslations } from "next-intl";
import { SelectCard, Text } from "@opal/components";
import { Content, ResponsiveLayout, Section } from "@opal/layouts";
import {
  SvgBarChart,
  SvgClipboard,
  SvgFilePlus,
  SvgFileText,
  SvgSearch,
  SvgSpreadsheetFile,
} from "@opal/icons";
import { AGENT_PILOTS, type AgentPilotKind } from "@/lib/agents/pilots";

const templateIcons = {
  research: SvgSearch,
  "document-analysis": SvgFileText,
  reporting: SvgBarChart,
  "spreadsheet-analysis": SvgSpreadsheetFile,
  "meeting-recap": SvgClipboard,
};

export default function AgentTemplatePicker({
  value,
  onChange,
}: {
  value: AgentPilotKind | null;
  onChange: (kind: AgentPilotKind | null) => void;
}) {
  const t = useTranslations("agents");
  const workspace = useTranslations("workspaceUi");
  const templates = [
    { kind: "research", title: workspace("research") },
    { kind: "document-analysis", title: workspace("documentAnalysis") },
    { kind: "reporting", title: t("reporting.template") },
    { kind: "spreadsheet-analysis", title: t("spreadsheetAnalysis.template") },
    { kind: "meeting-recap", title: t("meetingRecap.template") },
  ] as const;

  return (
    <Section gap={2} alignItems="stretch" height="fit">
      <Text as="h2" font="main-content-emphasis">
        {t("editor.templates.title")}
      </Text>
      <ResponsiveLayout display="grid" className="gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <SelectCard
          role="button"
          tabIndex={0}
          aria-pressed={value === null}
          state={value === null ? "selected" : "empty"}
          onClick={() => onChange(null)}
        >
          <Content
            icon={SvgFilePlus}
            font="main-ui-action"
            title={t("editor.templates.scratch")}
            description={t("editor.templates.scratchDescription")}
          />
        </SelectCard>
        {templates.map(({ kind, title }) => (
          <SelectCard
            key={kind}
            role="button"
            tabIndex={0}
            aria-pressed={value === kind}
            state={value === kind ? "selected" : "empty"}
            onClick={() => onChange(kind)}
          >
            <Content
              icon={templateIcons[kind]}
              font="main-ui-action"
              title={title}
              description={t(`modals.viewer.pilotGuide.${kind}.output`)}
            />
          </SelectCard>
        ))}
      </ResponsiveLayout>
      {value && (
        <Text as="p" color="text-03" role="status">
          {AGENT_PILOTS[value].requiresKnowledge
            ? workspace("chooseKnowledgeLibrariesAndSaveTheAgentToRun")
            : t(value === "meeting-recap" ? "meetingRecap.setup" : "spreadsheetAnalysis.setup")}
        </Text>
      )}
    </Section>
  );
}
