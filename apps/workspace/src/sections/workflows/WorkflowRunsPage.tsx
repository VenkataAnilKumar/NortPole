"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { NavLink } from "@opal/navigation";
import { useSearchParams } from "@opal/navigation";
import { useFormatter, useTranslations } from "next-intl";
import useSWR from "swr";
import { Button } from "@opal/components";
import { SvgArrowRight, SvgClock, SvgFileText } from "@opal/icons";
import { SEARCH_PARAM_NAMES } from "@/app/app/services/searchParams";
import { errorHandlingFetcher, errorHandlingFetchWith, fetchErrorDetail } from "@/lib/fetcher";
import DocumentReviewDetails from "./DocumentReviewDetails";

interface ExpenseReviewRun {
  id: number;
  chat_session_id: string;
  file_name: string | null;
  created_at: string;
  status: "complete" | "needs_review" | "stopped" | "failed" | "running" | "interrupted";
  workflow: "expense_review" | "document_review";
  open_findings: number | null;
  revision_of: number | null;
  drive_source: { library_name: string; policy_title: string; version: string } | null;
}

interface ScheduledRun {
  id: string;
  schedule_id: string;
  name: string;
  created_at: string;
  trigger: "timer" | "manual" | "chat" | "retry" | "source" | null;
  outcome: string;
  reason: string | null;
  task_state: string | null;
  task_id: string | null;
  chat_session_id: string | null;
  chat_message_id: number | null;
  file_name: string | null;
  expense_review: boolean;
  retry_of_id: string | null;
  retry_id: string | null;
  can_retry: boolean;
  drive_source: (NonNullable<ExpenseReviewRun["drive_source"]> & { file_name: string }) | null;
}

interface Cursor { at: string; key: string }

interface WorkflowRunFeed {
  runs: (ExpenseReviewRun | ScheduledRun)[];
  next_before: Cursor | null;
}

const STATUS: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  plan_ready: "Plan ready",
  plan_failed: "Plan failed",
  failed: "Failed",
  interrupted: "Result unavailable",
  expired: "Expired",
  review_complete: "Complete",
  needs_review: "Needs review",
  paused: "Schedule paused",
  skipped: "Skipped",
  drive_skipped: "Skipped",
  no_new_csv: "No new file",
};

const TASK_STATUS: Record<string, string> = {
  draft: "Draft",
  planning: "Preparing plan",
  plan_review: "Plan ready",
  plan_accepted: "Plan accepted",
  plan_failed: "Plan failed",
  running: "Running",
  draft_ready: "Draft ready",
  run_failed: "Failed",
  approved: "Complete",
  cancelled: "Cancelled",
  superseded: "Replaced",
};

const APPROVAL: Record<string, string> = {
  plan_review: "Plan approval needed",
  draft_ready: "Draft approval needed",
  approved: "Approved",
};

const TRIGGER = { timer: "Timer", manual: "Run now", chat: "Chat", retry: "Retry", source: "Knowledge change" };

function chatRunUrl(chatId: string, message?: number | null): `/app?${string}` {
  const params = new URLSearchParams({ [SEARCH_PARAM_NAMES.CHAT_ID]: chatId });
  if (message != null) params.set("message", String(message));
  return `/app?${params}`;
}

const LINK_STYLE = "inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-text-05 hover:bg-background-neutral-02 focus-visible:outline";

function ScheduledRunRow({ run, focused, refresh }: { run: ScheduledRun; focused: boolean; refresh: () => void }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const date = useFormatter();
  const [pending, setPending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [retryId, setRetryId] = useState<string | null>(null);
  const taskStatus = run.task_state && ["plan_ready", "plan_failed"].includes(run.outcome) && TASK_STATUS[run.task_state];
  const status = taskStatus || STATUS[run.outcome] || run.outcome;
  const approval = run.task_state ? APPROVAL[run.task_state] : null;
  const retry = run.retry_id ?? retryId;

  async function act(action: "retry" | "check-outcome") {
    setPending(true);
    setProblem(null);
    setDetail(null);
    try {
      const url = `/api/workflow-schedules/${run.schedule_id}/runs/${run.id}/${action}`;
      if (action === "retry") {
        const result = await errorHandlingFetchWith<{ id: string }>(url, { method: "POST" });
        setRetryId(result.id);
      } else {
        const result = await errorHandlingFetchWith<{ detail: string }>(url, { method: "POST" });
        setDetail(result.detail);
      }
    } catch (error) {
      setProblem(fetchErrorDetail(error) ?? "The request could not be completed.");
    } finally {
      setPending(false);
      refresh();
    }
  }

  return (
    <li
      id={`workflow-run-${run.id}`}
      tabIndex={focused ? -1 : undefined}
      className="flex flex-wrap items-center gap-3 p-3 focus-visible:outline sm:p-4"
    >
      <SvgClock aria-hidden="true" className="size-5 shrink-0 text-text-03" />
      <div className="min-w-0 flex-1">
        <p className="break-words text-sm font-medium text-text-05">{run.name}</p>
        <p className="text-xs text-text-03">
          {run.trigger ? TRIGGER[run.trigger] : "Earlier run"}
          {run.expense_review && " · Expense Review"} ·{" "}
          <time dateTime={run.created_at}>
            {date.dateTime(new Date(run.created_at), { dateStyle: "medium", timeStyle: "short" })}
          </time>
        </p>
        {approval && <p className="text-xs text-text-03">{approval}</p>}
        {run.reason && <p className="break-words text-xs text-text-03">{run.reason}</p>}
        {detail && !run.reason?.includes(detail) && <p role="status" className="text-xs text-text-03">{detail}</p>}
        {problem && <p role="alert" className="text-xs text-status-text-error-05">{problem}</p>}
        {run.file_name && !run.drive_source && <p className="break-words text-xs text-text-03">{run.file_name}</p>}
        {run.drive_source && (
          <p className="break-words text-xs text-text-03">
            {run.drive_source.file_name}{" "}{workspaceText("googleDriveVersion")}{" "}{run.drive_source.version} · {run.drive_source.library_name}
            {run.drive_source.policy_title && ` · ${run.drive_source.policy_title}`}
          </p>
        )}
      </div>
      <span className="rounded-full bg-background-neutral-02 px-2 py-1 text-xs text-text-05">{status}</span>
      {run.can_retry && !retry && (
        <Button prominence="secondary" disabled={pending} onClick={() => void act("retry")}>
          {pending ? "Retrying…" : "Retry"}
        </Button>
      )}
      {run.outcome === "interrupted" && (
        <Button prominence="secondary" disabled={pending} onClick={() => void act("check-outcome")}>
          {pending ? "Checking…" : "Check outcome"}
        </Button>
      )}
      {retry && <NavLink href={`/app/workflows/runs?run=${encodeURIComponent(retry)}`} className={LINK_STYLE}>{workspaceText("openRetry")}</NavLink>}
      {run.retry_of_id && <NavLink href={`/app/workflows/runs?run=${encodeURIComponent(run.retry_of_id)}`} className={LINK_STYLE}>{workspaceText("originalRun")}</NavLink>}
      {run.task_id ? (
        <NavLink href={`/app/workflows/drafts?task=${encodeURIComponent(run.task_id)}`} className={LINK_STYLE}>{workspaceText("openDraft")}{" "}<SvgArrowRight aria-hidden="true" className="size-4" />
        </NavLink>
      ) : run.chat_session_id ? (
        <NavLink href={chatRunUrl(run.chat_session_id, run.chat_message_id)} className={LINK_STYLE}>{workspaceText("openChat")}{" "}<SvgArrowRight aria-hidden="true" className="size-4" />
        </NavLink>
      ) : (
        <NavLink href={`/app/workflows/scheduled?schedule=${encodeURIComponent(run.schedule_id)}&run=${encodeURIComponent(run.id)}`} className={LINK_STYLE}>{workspaceText("openSchedule")}{" "}<SvgArrowRight aria-hidden="true" className="size-4" />
        </NavLink>
      )}
    </li>
  );
}

export default function WorkflowRunsPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const t = useTranslations("chat.workflowRuns");
  const date = useFormatter();
  const [cursors, setCursors] = useState<Cursor[]>([]);
  const params = useSearchParams();
  const review = params?.get("review");
  const requestedRun = params?.get("run");
  const runId = requestedRun && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(requestedRun)
    ? requestedRun.toLowerCase() : null;
  const requestedId = review && /^\d+$/.test(review) ? Number(review) : 0;
  const reviewId = Number.isSafeInteger(requestedId) ? requestedId : 0;
  const cursor = cursors.at(-1);
  const query = new URLSearchParams();
  if (cursor) {
    query.set("before_at", cursor.at);
    query.set("before_key", cursor.key);
  } else if (runId) {
    query.set("include_run", runId);
  }
  const { data, error, mutate } = useSWR<WorkflowRunFeed>(
    reviewId ? null : `/api/chat/workflow-run-feed?${query}`,
    errorHandlingFetcher,
    {
      refreshInterval: (feed) => feed?.runs.some((run) =>
        "outcome" in run ? run.outcome === "queued" || run.outcome === "running" || run.task_state === "running" : run.status === "running",
      ) ? 4000 : 0,
    },
  );
  const nextCursor = data?.next_before;
  const hasSelectedRun = !cursor && data?.runs.some(({ id }) => id === runId);
  useEffect(() => setCursors([]), [runId]);
  useEffect(() => {
    if (hasSelectedRun) document.getElementById(`workflow-run-${runId}`)?.focus();
  }, [hasSelectedRun, runId]);
  if (reviewId > 0) return <DocumentReviewDetails key={reviewId} reviewId={reviewId} />;

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 sm:p-8">
      <header>
        <h1 className="text-xl font-semibold text-text-05">{t("heading")}</h1>
        <p className="mt-1 text-sm text-text-03">{workspaceText("seeWhatRanFromChatRunNowASchedule")}</p>
      </header>
      {error ? (
        <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
          <p role="alert" className="text-sm text-text-03">
            {t("error")}
          </p>
          <Button prominence="secondary" onClick={() => void mutate()}>
            {t("retry")}
          </Button>
        </ResponsiveLayout>
      ) : !data ? (
        <output className="text-sm text-text-03">{t("loading")}</output>
      ) : data.runs.length ? (
        <ul
          aria-label={t("heading")}
          className="divide-y divide-border-01 rounded-xl border border-border-01"
        >
          {data.runs.map((run) => {
            if ("outcome" in run) {
              return <ScheduledRunRow key={run.id} run={run} focused={!cursor && run.id === runId} refresh={() => void mutate()} />;
            }
            const file = run.file_name ?? t("unknownFile");
            const workflow = run.workflow === "document_review"
              ? run.revision_of ? "Document Review revision" : "Document Review"
              : "Expense Review";
            return (
              <li key={run.id} className="flex flex-wrap items-center gap-3 p-3 sm:p-4">
                <SvgFileText aria-hidden="true" className="size-5 shrink-0 text-text-03" />
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm font-medium text-text-05">{file}</p>
                  <p className="text-xs text-text-03">
                    {workflow}{" "}{workspaceText("chat")}{" "}
                    <time dateTime={run.created_at}>
                      {date.dateTime(new Date(run.created_at), {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </time>
                    {run.open_findings != null && ` · ${run.open_findings} open ${run.open_findings === 1 ? "finding" : "findings"}`}
                  </p>
                  {run.drive_source && (
                    <p className="break-words text-xs text-text-03">{workspaceText("googleDriveVersion_88c186")}{" "}{run.drive_source.version} · {run.drive_source.library_name}
                      {run.drive_source.policy_title && ` · ${run.drive_source.policy_title}`}
                    </p>
                  )}
                </div>
                <span className="rounded-full bg-background-neutral-02 px-2 py-1 text-xs text-text-05">
                  {run.status === "running" || run.status === "interrupted" ? STATUS[run.status] : t(run.status)}
                </span>
                {run.workflow === "document_review" && (run.status === "complete" || run.status === "needs_review") && (
                  <NavLink href={`/app/workflows/runs?review=${run.id}`}
                    className="inline-flex items-center rounded-md px-2 py-1 text-sm font-medium text-text-05 hover:bg-background-neutral-02 focus-visible:outline">{workspaceText("viewFindings")}</NavLink>
                )}
                <NavLink
                  href={chatRunUrl(run.chat_session_id, run.id)}
                  aria-label={t("openFileChat", { file })}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-text-05 hover:bg-background-neutral-02 focus-visible:outline"
                >
                  {t("openChat")}
                  <SvgArrowRight aria-hidden="true" className="size-4" />
                </NavLink>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-text-03">{workspaceText("noWorkflowRunsYet")}</p>
      )}
      {(cursors.length > 0 || nextCursor) && (
        <ResponsiveLayout display="flex" className="gap-2">
          <Button
            prominence="secondary"
            disabled={!cursors.length}
            onClick={() => setCursors(cursors.slice(0, -1))}
          >
            {t("previous")}
          </Button>
          <Button
            prominence="secondary"
            disabled={!nextCursor}
            onClick={() => nextCursor && setCursors([...cursors, nextCursor])}
          >
            {t("next")}
          </Button>
        </ResponsiveLayout>
      )}
    </section>
  );
}
