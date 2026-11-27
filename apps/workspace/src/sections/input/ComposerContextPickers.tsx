"use client";

import { ActionButton } from "@opal/components";
import { useTranslations } from "next-intl";
import { Dropdown } from "@opal/components";
import { SvgChevronDownSmall, SvgFolder, SvgManageAgent } from "@opal/icons";
import type { IconFunctionComponent } from "@opal/types";
import type { MinimalAgent } from "@/lib/agents/types";
import { DEFAULT_AGENT_ID } from "@/lib/constants";
import type { Project } from "@/lib/projects/types";
import { useSettings } from "@/lib/settings/hooks";

interface ComposerContextPickersProps {
  agents: MinimalAgent[];
  activeAgent: MinimalAgent | undefined;
  projects: Project[];
  projectId: number | null;
  projectsLoading: boolean;
  projectsFailed: boolean;
  onAgentChange: (id: number) => void;
  onProjectChange: (id: number | null) => void;
}

function ContextTrigger({
  icon: Icon,
  label,
  name,
}: {
  icon: IconFunctionComponent;
  label: string;
  name: string;
}) {
  return (
    <Dropdown.Trigger asChild>
      <ActionButton
        type="button"
        aria-label={label}
        title={name}
        className="flex min-h-8 min-w-0 max-w-full items-center gap-1.5 rounded-lg px-2 text-sm text-text-04 hover:bg-background-neutral-01 focus-visible:outline-2 aria-expanded:bg-background-neutral-01"
      >
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        <span className="truncate">{name}</span>
        <SvgChevronDownSmall aria-hidden="true" className="size-3 shrink-0" />
      </ActionButton>
    </Dropdown.Trigger>
  );
}

export default function ComposerContextPickers({
  agents,
  activeAgent,
  projects,
  projectId,
  projectsLoading,
  projectsFailed,
  onAgentChange,
  onProjectChange,
}: ComposerContextPickersProps) {
  const t = useTranslations("chat.composerContext");
  const settings = useSettings();
  const project = projects.find(({ id }) => id === projectId);
  const agentOptions = agents
    .filter(({ id }) => !settings.disable_default_assistant || id !== DEFAULT_AGENT_ID)
    .map(({ id, name }) => ({ kind: "option" as const, value: String(id), title: name }));
  const projectOptions = projects.map(({ id, name }) => ({
    kind: "option" as const,
    value: String(id),
    title: name,
  }));

  return (
    <>
      <Dropdown side="top" disabled={!agentOptions.length}>
        <ContextTrigger
          icon={SvgManageAgent}
          label={activeAgent ? t("selectedAgent", { name: activeAgent.name }) : t("agent")}
          name={activeAgent?.name ?? t("agent")}
        />
        <Dropdown.Data
          label={t("agent")}
          search={{ placeholder: t("searchAgents") }}
          value={activeAgent ? String(activeAgent.id) : ""}
          items={agentOptions}
          onSelect={({ value }) => onAgentChange(Number(value))}
        />
      </Dropdown>
      <Dropdown side="top">
        <ContextTrigger
          icon={SvgFolder}
          label={project ? t("selectedProject", { name: project.name }) : t("chooseProject")}
          name={project?.name ?? t("chooseProject")}
        />
        <Dropdown.Data
          label={t("project")}
          search={{ placeholder: t("searchProjects") }}
          value={projectId === null ? "" : String(projectId)}
          items={[
            { kind: "option", value: "", title: t("noProject"), pinned: true },
            ...projectOptions,
            ...(projectsLoading || projectsFailed || !projects.length
              ? [
                  {
                    kind: "option" as const,
                    value: "status",
                    title: t(
                      projectsLoading
                        ? "loadingProjects"
                        : projectsFailed
                          ? "projectsUnavailable"
                          : "noProjects",
                    ),
                    disabled: true,
                  },
                ]
              : []),
          ]}
          onSelect={({ value }) => onProjectChange(value ? Number(value) : null)}
        />
      </Dropdown>
    </>
  );
}
