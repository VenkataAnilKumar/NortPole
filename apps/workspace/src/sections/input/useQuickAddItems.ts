import { useTranslations } from "next-intl";
import useSWR from "swr";
import type { DropdownMenuItem, DropdownMenuRow } from "@opal/components";
import { useNavigation } from "@opal/navigation";
import { useRef } from "react";
import { SvgArrowLeft, SvgBookOpen, SvgClock, SvgSparkle, SvgWorkflow } from "@opal/icons";
import { toast } from "@opal/layouts";
import { useDocumentSets } from "@/app/admin/documents/sets/hooks";
import type { ComposerSelection } from "@/app/app/types";
import type { MinimalAgent } from "@/lib/agents/types";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { createTemplateDraft } from "@/lib/packs/templateDraft";
import type { SkillsList } from "@/lib/skills/types";
import { SWR_KEYS } from "@/lib/swr-keys";
import { SEARCH_TOOL_ID } from "@/lib/tools/constants";

interface RecentTask {
  id: string;
  title: string;
  request: string;
  desired_output: string;
  withheld: boolean;
  updated_at: string;
}

interface WorkflowPack {
  pack_id: string;
  name: string;
  review_rules?: unknown[];
  ready_on_current_route: boolean;
  templates: { id: string; title: string }[];
}

export function useQuickAddItems({
  enabled,
  agent,
  select,
  insertPrompt,
  openExpenseReview,
  openDocumentReview,
}: {
  enabled: boolean;
  agent?: MinimalAgent;
  select: (selection: ComposerSelection) => void;
  insertPrompt: (prompt: string) => void;
  openExpenseReview: () => void;
  openDocumentReview: () => void;
}): { items?: DropdownMenuItem[]; libraries: { id: number; name: string }[]; reviewPacks: WorkflowPack[] } {
  const t = useTranslations("chat.quickAdd");
  const workflowCopy = useTranslations("chat.expenseReview");
  const navigation = useNavigation();
  const creatingDraft = useRef(false);
  const collections = useDocumentSets(false, enabled);
  const skills = useSWR<SkillsList>(enabled ? SWR_KEYS.userSkills : null, errorHandlingFetcher);
  const tasks = useSWR<RecentTask[]>(enabled ? "/api/tasks" : null, errorHandlingFetcher);
  const packs = useSWR<WorkflowPack[]>(enabled ? "/api/packs" : null, errorHandlingFetcher);
  const scheduling = useSWR<{ scheduling_allowed: boolean }>(
    enabled ? "/api/workflow-schedules" : null,
    errorHandlingFetcher,
  );
  if (!enabled) return { libraries: [], reviewPacks: [] };

  const supportsKnowledge = agent?.tools.some(
    (tool) => tool.enabled && tool.in_code_tool_id === SEARCH_TOOL_ID,
  );
  const agentCollections = agent?.document_sets ?? [];
  const libraries = (collections.data ?? []).filter(
    (collection) =>
      !agentCollections.length || agentCollections.some(({ id }) => id === collection.id),
  );
  const knowledgeRows: DropdownMenuRow[] = libraries.map(({ name, description }) => ({
    kind: "action",
    id: name,
    title: name,
    description,
    onSelect: () => select({ kind: "knowledge", id: name, label: name }),
  }));
  const skillRows: DropdownMenuRow[] = [
    ...(skills.data?.builtins ?? []),
    ...(skills.data?.customs ?? []),
  ]
    .filter(
      (skill) =>
        skill.enabled &&
        skill.is_valid !== false &&
        skill.is_available !== false &&
        !skill.external_app,
    )
    .map(({ id, name, description }) => ({
      kind: "action",
      id,
      title: name,
      description,
      onSelect: () => select({ kind: "skill", id, label: name }),
    }));
  const taskRows: DropdownMenuRow[] = (tasks.data ?? [])
    .filter((task) => !task.withheld && Boolean(task.request?.trim()))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 8)
    .map((task) => ({
      kind: "action",
      id: task.id,
      title: task.title,
      onSelect: () =>
        insertPrompt([task.request, task.desired_output].filter(Boolean).join("\n\n")),
    }));

  const workflowRows: DropdownMenuRow[] = [
    ...(scheduling.data?.scheduling_allowed ? [{
      kind: "action" as const,
      id: "new-schedule",
      title: "New schedule",
      icon: SvgClock,
      onSelect: () => navigation.go("/app/workflows/scheduled?new=1"),
    }] : []),
    {
      kind: "action",
      id: "document-review",
      title: "Document Review",
      icon: SvgWorkflow,
      disabled: !supportsKnowledge,
      tooltip: supportsKnowledge ? undefined : t("knowledgeUnavailable"),
      onSelect: openDocumentReview,
    },
    {
      kind: "action",
      id: "expense-review",
      title: workflowCopy("title"),
      icon: SvgWorkflow,
      disabled: !supportsKnowledge,
      tooltip: supportsKnowledge ? undefined : t("knowledgeUnavailable"),
      onSelect: openExpenseReview,
    },
    ...(packs.data ?? [])
      .filter((pack) => pack.ready_on_current_route)
      .flatMap(({ pack_id, templates }) =>
        templates.map(
          ({ id, title }): DropdownMenuRow => ({
            kind: "action",
            id: `${pack_id}/${id}`,
            title,
            icon: SvgWorkflow,
            onSelect: async () => {
              if (creatingDraft.current) return;
              creatingDraft.current = true;
              try {
                navigation.go(await createTemplateDraft(pack_id, id));
              } catch {
                toast.error(workflowCopy("draftFailed"));
              } finally {
                creatingDraft.current = false;
              }
            },
          }),
        ),
      ),
  ];

  const items = [
    {
      id: "knowledge",
      label: t("knowledge"),
      icon: SvgBookOpen,
      rows: knowledgeRows,
      state: collections,
      disabled: !supportsKnowledge,
    },
    { id: "skills", label: t("skills"), icon: SvgSparkle, rows: skillRows, state: skills },
    {
      id: "workflows",
      label: workflowCopy("workflows"),
      icon: SvgWorkflow,
      rows: workflowRows,
      state: packs,
    },
    { id: "recent", label: t("recentTasks"), icon: SvgClock, rows: taskRows, state: tasks },
  ].map(
    ({ id, label, icon, rows, state, disabled }): DropdownMenuRow => ({
      kind: "action",
      id,
      title: label,
      icon,
      disabled,
      tooltip: disabled ? t("knowledgeUnavailable") : undefined,
      onSelect: (views) =>
        views.push({
          key: id,
          items: [
            {
              kind: "action",
              id: "back",
              title: t("back"),
              icon: SvgArrowLeft,
              pinned: true,
              onSelect: (stack) => stack.pop(),
            },
            {
              kind: "group",
              title: label,
              items: rows.length
                ? rows
                : [
                    {
                      kind: "action",
                      id: "status",
                      title: t(state.isLoading ? "loading" : state.error ? "unavailable" : "empty"),
                      disabled: true,
                      onSelect: () => {},
                    },
                  ],
            },
          ],
        }),
    }),
  );
  return { items, libraries, reviewPacks: (packs.data ?? []).filter((pack) => pack.review_rules?.length) };
}
