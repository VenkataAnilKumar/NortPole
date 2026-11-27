"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton } from "@opal/components";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useNavigation } from "@opal/navigation";
import { useTranslations } from "next-intl";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { createTemplateDraft } from "@/lib/packs/templateDraft";
import { cn } from "@opal/utils";
import {
  SvgArrowExchange,
  SvgBarChart,
  SvgBookOpen,
  SvgCalendar,
  SvgDashboard,
  SvgEdit,
  SvgFileText,
  SvgLineChartUp,
  SvgMoreHorizontal,
  SvgSearch,
  SvgSpreadsheetFile,
  SvgWorkflow,
  SvgX,
} from "@opal/icons";

// Keep the lazy chart bundle's loading boundary out of the Chat composer.
const CsvVisualizationModal = dynamic(
  () => import("@/sections/chat/CsvVisualizationModal"),
  { loading: () => null }
);
const PresentationModal = dynamic(
  () => import("@/sections/chat/PresentationModal"),
  { loading: () => null }
);
const SpreadsheetModal = dynamic(
  () => import("@/sections/chat/SpreadsheetModal"),
  { loading: () => null }
);
const DocumentModal = dynamic(() => import("@/sections/chat/DocumentModal"), { loading: () => null });

const STARTERS = [
  { id: "knowledge", Icon: SvgBookOpen, color: "text-violet-600 dark:text-violet-300" },
  { id: "research", Icon: SvgSearch, color: "text-cyan-700 dark:text-cyan-300" },
  { id: "document", Icon: SvgEdit, color: "text-rose-600 dark:text-rose-300" },
  { id: "data", Icon: SvgBarChart, color: "text-emerald-700 dark:text-emerald-300" },
] as const;

const CATEGORIES = [
  { id: "knowledge", tasks: [{ id: "policy", Icon: SvgBookOpen }] },
  { id: "research", tasks: [{ id: "compare", Icon: SvgArrowExchange }] },
  { id: "writing", tasks: [{ id: "presentation", Icon: SvgFileText, builder: "presentation" }] },
  {
    id: "data",
    tasks: [
      { id: "spreadsheet", Icon: SvgSpreadsheetFile, builder: "spreadsheet" },
      { id: "visualization", Icon: SvgLineChartUp, builder: "chart" },
      { id: "dashboard", Icon: SvgDashboard, builder: "dashboard" },
    ],
  },
  { id: "meetings", tasks: [{ id: "actionItems", Icon: SvgCalendar }] },
  { id: "automation", tasks: [{ id: "recurring", Icon: SvgWorkflow }] },
] as const;

const iconButtonClass =
  "group relative grid place-items-center rounded-xl border border-border-01 bg-background-neutral-00 hover:bg-background-neutral-01 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50";

interface ExplorePack {
  pack_id: string;
  name: string;
  group: "everyday" | "domain";
  ready_on_current_route: boolean;
  readiness_note: string | null;
  templates: { id: string; title: string }[];
}

function TaskHint({ children }: { children: string }) {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute start-1/2 top-full z-10 mt-1 hidden w-max max-w-32 -translate-x-1/2 rounded-lg border border-border-01 bg-background-neutral-00 px-2 py-1 text-center text-xs text-text-05 shadow-sm group-hover:block group-focus-visible:block rtl:translate-x-1/2"
    >
      {children}
    </span>
  );
}

export default function QuickStartCards({
  onPick,
  disabled = false,
}: {
  onPick: (prompt: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("chat.quickStart");
  const navigation = useNavigation();
  const id = useId();
  const sectionRef = useRef<HTMLElement>(null);
  const exploreRef = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [builder, setBuilder] = useState<"chart" | "dashboard" | "presentation" | "spreadsheet" | "document" | null>(null);
  const closeBuilder = () => {
    setBuilder(null);
    requestAnimationFrame(() => exploreRef.current?.focus());
  };
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [draftFailed, setDraftFailed] = useState(false);
  const { data: packs, error, isLoading } = useSWR<ExplorePack[]>(
    expanded ? "/api/packs" : null,
    errorHandlingFetcher
  );
  const templates = (packs ?? [])
    .filter((pack) => pack.templates.length > 0)
    .sort((a, b) => Number(b.group === "everyday") - Number(a.group === "everyday"));

  const close = useCallback(() => {
    setExpanded(false);
    exploreRef.current?.focus();
  }, []);

  useEffect(() => {
    const section = sectionRef.current;
    if (!expanded || !section) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
      }
    };
    section.addEventListener("keydown", dismiss);
    return () => section.removeEventListener("keydown", dismiss);
  }, [close, expanded]);

  const openWorkflow = async (packId: string, templateId: string) => {
    setCreatingDraft(true);
    setDraftFailed(false);
    try {
      navigation.go(await createTemplateDraft(packId, templateId));
    } catch {
      setDraftFailed(true);
      setCreatingDraft(false);
    }
  };

  return (
    <section
      className="mb-3 flex w-full flex-col gap-2"
      aria-label={t("heading")}
      ref={sectionRef}
    >
      <ResponsiveLayout display="flex" className="items-center justify-between">
        <h2 className="text-sm font-medium text-text-04">{t("heading")}</h2>
        <ActionButton
          ref={exploreRef}
          type="button"
          aria-label={t("explore")}
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => setExpanded(!expanded)}
          className={cn(iconButtonClass, "size-9")}
        >
          <SvgMoreHorizontal aria-hidden="true" className="size-4" />
          <TaskHint>{t("explore")}</TaskHint>
        </ActionButton>
      </ResponsiveLayout>
      <ResponsiveLayout display="grid" data-testid="quick-start-cards" className="grid-cols-4 gap-2 sm:gap-3">
        {STARTERS.map(({ id, Icon, color }) => {
          const label = t(`starters.${id}.label`);
          return (
            <ActionButton
              key={id}
              type="button"
              aria-label={label}
              disabled={disabled && id !== "document"}
              className={cn(iconButtonClass, "min-h-14 sm:min-h-16", color)}
              onClick={() => id === "document" ? setBuilder("document") : onPick(t(`starters.${id}.prompt`))}
            >
              <Icon aria-hidden="true" className="size-6" />
              <TaskHint>{label}</TaskHint>
            </ActionButton>
          );
        })}
      </ResponsiveLayout>
      <div
        id={id}
        hidden={!expanded}
        className="rounded-xl border border-border-01 bg-background-neutral-00 p-3"
      >
        <ResponsiveLayout display="flex" className="mb-2 items-center justify-between">
          <h3 className="text-sm font-semibold text-text-05">{t("explore")}</h3>
          <ActionButton
            type="button"
            aria-label={t("close")}
            onClick={close}
            className="grid size-8 place-items-center rounded-lg hover:bg-background-neutral-01 focus-visible:outline-2"
          >
            <SvgX aria-hidden="true" className="size-4" />
          </ActionButton>
        </ResponsiveLayout>
        <ResponsiveLayout display="grid" className="grid-cols-2 gap-2 sm:grid-cols-3">
          {CATEGORIES.map(({ id, tasks }) => (
            <section key={id} className="rounded-lg border border-border-01 p-2">
              <h4 className="mb-1 text-xs font-medium text-text-04">{t(`categories.${id}`)}</h4>
              <ResponsiveLayout display="flex" className="flex-wrap gap-1">
                {tasks.map((task) => {
                  const { id, Icon } = task;
                  const label = t(`tasks.${id}.label`);
                  const isLocalBuilder = "builder" in task;
                  return (
                    <ActionButton
                      key={id}
                      type="button"
                      aria-label={label}
                      disabled={disabled && !isLocalBuilder}
                      className={cn(iconButtonClass, "size-9 text-text-05")}
                      onClick={() => {
                        setExpanded(false);
                        if (isLocalBuilder) setBuilder(task.builder);
                        else onPick(t(`tasks.${task.id}.prompt`));
                      }}
                    >
                      <Icon aria-hidden="true" className="size-4" />
                      <TaskHint>{label}</TaskHint>
                    </ActionButton>
                  );
                })}
              </ResponsiveLayout>
            </section>
          ))}
        </ResponsiveLayout>
        {(isLoading || creatingDraft) && <output className="mt-2 block text-xs text-text-04">{t(creatingDraft ? "creatingDraft" : "loadingWorkflows")}</output>}
        {(draftFailed || (error && !packs)) && <p role="alert" className="mt-2 text-xs text-status-text-error-05">{t(draftFailed ? "draftFailed" : "workflowsUnavailable")}</p>}
        {templates.length > 0 && (
          <section className="mt-3 border-t border-border-01 pt-2" aria-label={t("templates")}>
            <h4 className="text-sm font-semibold text-text-05">{t("templates")}</h4>
            <ResponsiveLayout display="grid" className="mt-1 max-h-52 gap-2 overflow-y-auto sm:grid-cols-2">
              {templates.map((pack) => (
                <div key={pack.pack_id} className="min-w-0 rounded-lg border border-border-01 p-2">
                  <h5 className="break-words text-xs font-medium text-text-04">{pack.name}</h5>
                  {!pack.ready_on_current_route && pack.readiness_note && (
                    <p className="mt-1 text-xs text-text-03">{pack.readiness_note}</p>
                  )}
                  {pack.templates.map(({ id, title }) => (
                    <ActionButton key={id} type="button" disabled={creatingDraft || !pack.ready_on_current_route} onClick={() => void openWorkflow(pack.pack_id, id)} className="flex w-full items-start gap-2 rounded-md p-2 text-start text-sm text-text-05 hover:bg-background-neutral-01 focus-visible:outline-2 disabled:opacity-50">
                      <SvgWorkflow className="mt-0.5 size-4 shrink-0" aria-hidden="true" />{title}
                    </ActionButton>
                  ))}
                </div>
              ))}
            </ResponsiveLayout>
          </section>
        )}
      </div>
      {builder === "document" && <DocumentModal onClose={closeBuilder} />}
      {builder === "presentation" && <PresentationModal onClose={closeBuilder} />}
      {builder === "spreadsheet" && <SpreadsheetModal onClose={closeBuilder} />}
      {(builder === "chart" || builder === "dashboard") && <CsvVisualizationModal mode={builder} onClose={closeBuilder} />}
    </section>
  );
}
