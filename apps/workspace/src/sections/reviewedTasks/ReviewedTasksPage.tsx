"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeTextArea } from "@opal/components";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState } from "react";
import { useSearchParams } from "@opal/navigation";
import useSWR, { mutate as mutateCache } from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { invalidateNotificationCaches } from "@/lib/notifications/api";
import { SWR_KEYS } from "@/lib/swr-keys";
import TaskActions from "@/sections/reviewedTasks/TaskActions";

const URL = "/api/tasks";

type State = "draft" | "planning" | "plan_review" | "plan_accepted" | "plan_failed" | "running" | "draft_ready" | "run_failed" | "approved" | "cancelled" | "superseded";

interface Task {
  id: string;
  title: string;
  request: string;
  desired_output: string;
  state: State;
  version: number;
  plan: string[] | null;
  plan_route: string | null;
  plan_error: string | null;
  revision_note: string | null;
  updated_at: string;
  draft_text: string | null;
  draft_sources: { n: number; doc_id: string; title: string; link: string | null; cited: boolean; passage?: string; flagged?: boolean }[] | null;
  draft_route: string | null;
  run_error: string | null;
  draft_hash: string | null;
  draft_version: number | null;
  draft_versions: { v: number; by: "model" | "owner"; text: string; at: string }[] | null;
  withheld: boolean;
  withheld_message: string | null;
  rule_results?: { kind: string; severity: "block" | "warn"; message: string; passed: boolean; detail: string }[];
  draft_claims: { i: number; text: string; cites: number[]; status: "supported" | "unsupported" | "notice"; decision: "keep" | "remove" | null }[] | null;
  approved_at: string | null;
  exported_at: string | null;
}

const STATE_LABEL: Record<State, string> = {
  draft: "Draft",
  planning: "Planning",
  plan_review: "Plan to review",
  plan_accepted: "Plan accepted",
  plan_failed: "Plan failed",
  running: "Running",
  draft_ready: "Draft ready",
  run_failed: "Run failed",
  approved: "Approved",
  cancelled: "Cancelled",
  superseded: "Replaced by a newer scheduled run",
};
const ROUTE_LABEL: Record<string, string> = { local: "Local", private: "Private", cloud: "Cloud" };

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

type TaskRequest =
  | { title: string; request: string; desired_output: string; version?: number }
  | { version: number; note?: string; draft_hash?: string | null; decision?: "keep" | "remove" };

async function call(path: string, method: string, body: TaskRequest): Promise<Task> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `The change could not be saved (HTTP ${res.status}).`);
  }
  return res.json();
}

function DraftForm({
  task,
  onSaved,
  onCancel,
}: {
  task: Task | null;
  onSaved: (t: Task) => void;
  onCancel?: () => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [title, setTitle] = useState(task?.title ?? "");
  const [request, setRequest] = useState(task?.request ?? "");
  const [output, setOutput] = useState(task?.desired_output ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { title, request, desired_output: output };
      onSaved(task ? await call(`${URL}/${task.id}`, "PATCH", { ...body, version: task.version }) : await call(URL, "POST", body));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The draft could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResponsiveLayout display="flex" className="flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("title")}<NativeInput className={`${input} min-h-11`} value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("whatShouldThisDraftDo")}<NativeTextArea className={input} rows={4} value={request} maxLength={8000} onChange={(e) => setRequest(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("desiredOutput")}{" "}<span className="font-normal text-text-03">(optional)</span>
        <NativeInput className={`${input} min-h-11`} value={output} maxLength={8000} onChange={(e) => setOutput(e.target.value)} />
      </label>
      {error && <p role="alert" className="text-sm text-status-text-error-05">{error}</p>}
      <ResponsiveLayout display="flex" className="flex-wrap gap-2">
        <ActionButton type="button" className={primary} disabled={busy || !title.trim() || !request.trim()} onClick={save}>
          {busy ? "Saving…" : "Save draft"}
        </ActionButton>
        {onCancel && (
          <ActionButton type="button" className={secondary} disabled={busy} onClick={onCancel}>{workspaceText("cancel")}</ActionButton>
        )}
      </ResponsiveLayout>
      <p className="text-xs text-text-03">{workspaceText("savingADraftRunsNothingWorkBeginsOnlyWhen")}</p>
    </ResponsiveLayout>
  );
}

function TaskDetail({ task, onChange }: { task: Task; onChange: () => Promise<void> }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editingDraft, setEditingDraft] = useState(false);
  const [draftText, setDraftText] = useState(task.draft_text ?? "");
  const latestBy = task.draft_versions?.[task.draft_versions.length - 1]?.by ?? "model";
  const openClaims = (task.draft_claims ?? []).filter((c) => c.status === "unsupported" && c.decision === null).length;

  const exportDraft = async () => {
    setBusy("export");
    setError(null);
    try {
      const res = await fetch(`${URL}/${task.id}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: task.version }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Export failed (HTTP ${res.status}).`);
      const blob = new Blob([data.markdown], { type: "text/markdown" });
      const href = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = data.filename;
      a.click();
      window.URL.revokeObjectURL(href);
      await onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed.");
    } finally {
      setBusy(null);
    }
  };

  const act = async (name: string, path: string, body: TaskRequest) => {
    setBusy(name);
    setError(null);
    try {
      await call(`${URL}/${task.id}${path}`, "POST", body);
      await onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The change could not be saved.");
      await onChange();
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className={card} data-testid="task-detail" aria-labelledby="task-title">
      <ResponsiveLayout display="flex" className="mb-3 flex-wrap items-start justify-between gap-3">
        <h2 id="task-title" className="min-w-0 text-lg font-semibold text-text-05">{task.title}</h2>
        <span data-testid="task-state" className="rounded-full border border-border-01 px-2.5 py-0.5 text-xs font-medium text-text-03">
          {STATE_LABEL[task.state]}
        </span>
      </ResponsiveLayout>

      {editing ? (
        <DraftForm
          task={task}
          onSaved={async () => {
            setEditing(false);
            await onChange();
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <p className="whitespace-pre-wrap text-sm text-text-05">{task.request}</p>
          {task.desired_output && <p className="mt-2 text-sm text-text-03">{workspaceText("desiredOutput_2668fe")}{" "}{task.desired_output}</p>}
          {task.revision_note && task.state === "draft" && (
            <p className="mt-3 rounded-xl bg-background-neutral-01 px-3 py-2 text-sm text-text-05">{workspaceText("yourRevisionNote")}{" "}{task.revision_note}
            </p>
          )}
        </>
      )}

      {task.plan && task.state !== "draft" && (
        <section className="mt-4" aria-labelledby="plan-h">
          <h3 id="plan-h" className="mb-2 text-sm font-semibold text-text-05">{workspaceText("proposedPlan")}{task.plan_route && (
              <span className="ml-2 font-normal text-text-03">{workspaceText("draftedOnThe")}{" "}{ROUTE_LABEL[task.plan_route] ?? task.plan_route} route</span>
            )}
          </h3>
          {task.plan.some((s) => s.startsWith("Search: ")) && (
            <p className="mb-2 text-xs text-text-03" data-testid="agent-plan-note">{workspaceText("thisWorkflowIsRunByAnAgentAfterYou")}</p>
          )}
          <ol className="list-decimal space-y-1 pl-5 text-sm text-text-05" data-testid="task-plan">
            {task.plan.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </section>
      )}
      {task.withheld && (
        <p role="alert" data-testid="task-withheld" className="mt-4 rounded-xl bg-background-neutral-01 px-3 py-2 text-sm text-text-05">
          {task.withheld_message}
        </p>
      )}
      {task.draft_text && (task.state === "draft_ready" || task.state === "approved") && (
        <section className="mt-5 border-t border-border-01 pt-4" aria-labelledby="draft-h" data-testid="task-draft">
          <h3 id="draft-h" className="mb-2 text-sm font-semibold text-text-05">{workspaceText("draft")}<span className="ml-2 font-normal text-text-03" data-testid="draft-version">
              version {task.draft_version ?? 1}
              {latestBy === "owner"
                ? " · edited by you"
                : task.draft_route
                  ? ` · written on the ${ROUTE_LABEL[task.draft_route] ?? task.draft_route} route`
                  : ""}
            </span>
          </h3>
          {editingDraft ? (
            <ResponsiveLayout display="flex" className="flex-col gap-2">
              <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("editTheDraftCiteOnlyTheNumberedSourcesBelow")}<NativeTextArea
                  className={input}
                  rows={6}
                  maxLength={20000}
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                />
              </label>
              <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                <ActionButton
                  type="button"
                  className={primary}
                  disabled={!!busy || !draftText.trim()}
                  onClick={async () => {
                    setBusy("save-draft");
                    setError(null);
                    try {
                      const res = await fetch(`${URL}/${task.id}/draft`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ version: task.version, text: draftText }),
                      });
                      const data = await res.json().catch(() => null);
                      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Save failed (HTTP ${res.status}).`);
                      setEditingDraft(false);
                      await onChange();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Save failed.");
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  {busy === "save-draft" ? "Saving…" : "Save as a new version"}
                </ActionButton>
                <ActionButton type="button" className={secondary} disabled={!!busy} onClick={() => setEditingDraft(false)}>{workspaceText("cancel")}</ActionButton>
              </ResponsiveLayout>
            </ResponsiveLayout>
          ) : task.draft_claims && task.draft_claims.length > 0 ? (
            <ul className="flex flex-col gap-2" data-testid="task-claims">
              {task.draft_claims.map((c) => {
                const removed = c.decision === "remove";
                const needsDecision = c.status === "unsupported" && c.decision === null && task.state === "draft_ready";
                return (
                  <li
                    key={c.i}
                    className={`rounded-xl border px-3 py-2 text-sm ${c.status === "unsupported" ? "border-status-warning-02" : "border-border-01"}`}
                  >
                    <span className={removed ? "text-text-03 line-through" : "text-text-05"}>{c.text}</span>
                    <span className="ml-2 text-xs text-text-03">
                      {c.status === "notice"
                        ? "notice"
                        : c.status === "supported"
                        ? "supported"
                        : removed
                          ? "unsupported · removed"
                          : c.decision === "keep"
                            ? "unsupported · kept, labelled in the export"
                            : "unsupported · needs your decision"}
                    </span>
                    {needsDecision && (
                      <ResponsiveLayout as="span" display="inlineFlex" className="ml-2 gap-1">
                        <ActionButton
                          type="button"
                          className="min-h-9 rounded-lg border border-border-02 px-3 text-xs font-semibold text-text-05 disabled:opacity-50"
                          disabled={!!busy}
                          onClick={() => act(`keep-${c.i}`, `/claims/${c.i}`, { version: task.version, decision: "keep" })}
                        >{workspaceText("keep")}</ActionButton>
                        <ActionButton
                          type="button"
                          className="min-h-9 rounded-lg border border-border-02 px-3 text-xs font-semibold text-text-05 disabled:opacity-50"
                          disabled={!!busy}
                          onClick={() => act(`remove-${c.i}`, `/claims/${c.i}`, { version: task.version, decision: "remove" })}
                        >{workspaceText("remove")}</ActionButton>
                      </ResponsiveLayout>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="whitespace-pre-wrap text-sm text-text-05">{task.draft_text}</p>
          )}
          {task.draft_sources && task.draft_sources.length > 0 ? (
            <ol className="mt-3 space-y-1 text-xs text-text-03" aria-label={workspaceText("sources")} data-testid="task-sources">
              {task.draft_sources.map((src) => (
                <li key={src.n}>
                  [{src.n}]{" "}
                  {src.link ? (
                    <a className="underline" href={src.link} target="_blank" rel="noreferrer">{src.title}</a>
                  ) : (
                    src.title
                  )}
                  {!src.cited && <span className="ml-1">{workspaceText("foundButNotCited")}</span>}
                  {src.flagged && (
                    <span className="ml-2 text-status-text-warning-05" data-testid="source-flagged">{workspaceText("containsTextThatReadsLikeAnInstructionToThe")}</span>
                  )}
                  {src.passage && (
                    <details className="mt-1">
                      <summary className="cursor-pointer">{workspaceText("passageTheModelSaw")}</summary>
                      <p className="mt-1 whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1">{src.passage}</p>
                    </details>
                  )}
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-xs text-text-03">{workspaceText("noPermittedSourceWasFoundForThisRequest")}</p>
          )}
          <p className="mt-3 text-xs text-text-03">
            {task.state === "approved"
              ? `You approved exactly this draft${task.approved_at ? ` on ${new Date(task.approved_at).toLocaleString()}` : ""}. Export checks your access to each cited source again.`
              : "Only sources you can open were used. Approving covers exactly this draft; a new run needs a new approval."}
          </p>
          {task.state === "draft_ready" && !editingDraft && !task.withheld && (
            <ActionButton
              type="button"
              className={`${secondary} mt-3`}
              disabled={!!busy}
              onClick={() => {
                setDraftText(task.draft_text ?? "");
                setEditingDraft(true);
              }}
            >{workspaceText("editDraft")}</ActionButton>
          )}
          {task.draft_versions && task.draft_versions.length > 1 && (
            <details className="mt-3 text-xs text-text-03" data-testid="draft-history">
              <summary className="cursor-pointer">{workspaceText("previousVersions")}{task.draft_versions.length - 1})</summary>
              <ol className="mt-2 space-y-2">
                {task.draft_versions.slice(0, -1).reverse().map((v) => (
                  <li key={v.v} className="rounded-lg border border-border-01 px-3 py-2">
                    <div className="font-medium text-text-05">{workspaceText("version_2da600")}{" "}{v.v} · {v.by === "owner" ? "edited by you" : "written by the model"} · {new Date(v.at).toLocaleString()}
                    </div>
                    <p className="mt-1 whitespace-pre-wrap">{v.text}</p>
                  </li>
                ))}
              </ol>
            </details>
          )}
          {task.exported_at && (
            <p className="mt-1 text-xs text-text-03" data-testid="task-exported">{workspaceText("lastExported")}{" "}{new Date(task.exported_at).toLocaleString()}.
            </p>
          )}
        </section>
      )}
      {task.state === "run_failed" && task.run_error && (
        <p role="alert" className="mt-4 text-sm text-status-text-error-05">{task.run_error}</p>
      )}
      {task.state === "plan_failed" && task.plan_error && (
        <p role="alert" className="mt-4 text-sm text-status-text-error-05">{task.plan_error}</p>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-status-text-error-05">{error}</p>}

      {!editing && (
        <ResponsiveLayout display="flex" className="mt-4 flex-wrap gap-2">
          {task.state === "draft" && (
            <>
              <ActionButton type="button" className={primary} disabled={!!busy} onClick={() => act("start", "/start", { version: task.version })}>
                {busy === "start" ? "Drafting a plan…" : "Start"}
              </ActionButton>
              <ActionButton type="button" className={secondary} disabled={!!busy} onClick={() => setEditing(true)}>{workspaceText("edit")}</ActionButton>
            </>
          )}
          {task.state === "plan_review" && (
            <ActionButton type="button" className={primary} disabled={!!busy} onClick={() => act("accept", "/plan/accept", { version: task.version })}>
              {busy === "accept" ? "Accepting…" : "Accept plan"}
            </ActionButton>
          )}
          {(task.state === "plan_review" || task.state === "plan_failed") && (
            <ResponsiveLayout display="flex" className="w-full flex-wrap items-end gap-2">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("whatShouldChange")}<NativeInput className={`${input} min-h-11`} value={note} maxLength={8000} onChange={(e) => setNote(e.target.value)} />
              </label>
              <ActionButton type="button" className={secondary} disabled={!!busy} onClick={() => act("revise", "/plan/revise", { version: task.version, note })}>{workspaceText("revise")}</ActionButton>
            </ResponsiveLayout>
          )}
          {(task.rule_results ?? []).length > 0 && (
            <ul className="w-full text-sm" data-testid="rule-results" aria-label={workspaceText("packReviewRules")}>
              {(task.rule_results ?? []).map((r, i) => (
                <li key={i} className={r.passed ? "text-text-03" : r.severity === "block" ? "text-status-text-error-05" : "text-status-text-warning-05"}>
                  {r.passed ? "Met" : r.severity === "block" ? "Not met (must be fixed to approve)" : "Warning"}: {r.message} <span className="text-xs">({r.detail})</span>
                </li>
              ))}
            </ul>
          )}
          {task.state === "draft_ready" && task.draft_hash && !task.withheld && (
            <ActionButton
              type="button"
              className={primary}
              disabled={!!busy || openClaims > 0 || (task.rule_results ?? []).some((r) => !r.passed && r.severity === "block")}
              title={openClaims > 0 ? `Decide on ${openClaims} unsupported claim(s) first` : (task.rule_results ?? []).some((r) => !r.passed && r.severity === "block") ? "The pack's review rules are not met" : undefined}
              onClick={() => act("approve", "/approve", { version: task.version, draft_hash: task.draft_hash })}
            >
              {busy === "approve" ? "Approving…" : openClaims > 0 ? `Approve (${openClaims} claim${openClaims === 1 ? "" : "s"} to decide)` : "Approve this draft"}
            </ActionButton>
          )}
          {task.state === "approved" && (
            <ActionButton type="button" className={primary} disabled={!!busy} onClick={exportDraft}>
              {busy === "export" ? "Checking access…" : "Export as Markdown"}
            </ActionButton>
          )}
          {(task.state === "approved" || task.state === "draft_ready") && (
            <NavLink href={`/app/workflows/scheduled?task=${encodeURIComponent(task.id)}`} className={`${secondary} inline-flex items-center`} data-testid="repeat-on-schedule">{workspaceText("repeatOnASchedule")}</NavLink>
          )}
          {task.state === "draft_ready" && (
            <ResponsiveLayout display="flex" className="w-full flex-wrap items-end gap-2">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("whatShouldChange")}<NativeInput className={`${input} min-h-11`} value={note} maxLength={8000} onChange={(e) => setNote(e.target.value)} />
              </label>
              <ActionButton type="button" className={secondary} disabled={!!busy} onClick={() => act("revise", "/plan/revise", { version: task.version, note })}>{workspaceText("revise")}</ActionButton>
            </ResponsiveLayout>
          )}
          {(task.state === "plan_accepted" || task.state === "run_failed") && (
            <ActionButton type="button" className={primary} disabled={!!busy} onClick={() => act("run", "/run", { version: task.version })}>
              {busy === "run" ? "Gathering sources and drafting…" : task.state === "run_failed" ? "Try again" : "Run plan"}
            </ActionButton>
          )}
          {(task.state === "draft" || task.state === "plan_review" || task.state === "plan_failed" || task.state === "plan_accepted" || task.state === "run_failed" || task.state === "draft_ready") && (
            <ActionButton type="button" className={`${secondary} ml-auto`} disabled={!!busy} onClick={() => act("cancel", "/cancel", { version: task.version })}>{workspaceText("cancelDraft")}</ActionButton>
          )}
        </ResponsiveLayout>
      )}
      {task.state === "approved" && !task.withheld && <TaskActions taskId={task.id} />}
      {task.state === "plan_accepted" && (
        <p className="mt-4 text-sm text-text-03">{workspaceText("planAcceptedRunItToGatherSourcesYouCan")}</p>
      )}
    </article>
  );
}

/**
 * Drafts (reviewed work; the API and code still call them tasks): write a draft, start it on purpose, review the proposed plan,
 * then accept, revise or cancel. Nothing runs before Start, and the plan is
 * drafted only on a route the administrator's policy allows.
 */
export default function ReviewedTasksPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, error, isLoading, mutate } = useSWR<Task[]>(URL, errorHandlingFetcher);
  const params = useSearchParams();
  const [selected, setSelected] = useState<string | null>(params.get("task"));
  const [creating, setCreating] = useState(false);
  const tasks = data ?? [];
  const listedTask = tasks.find((t) => t.id === selected);
  const { data: linkedTask, error: linkedError, mutate: refreshLinkedTask } = useSWR<Task>(
    !isLoading && selected && !listedTask ? `${URL}/${encodeURIComponent(selected)}` : null,
    errorHandlingFetcher
  );
  const current = listedTask ?? linkedTask;
  const refreshTasks = async () => {
    await Promise.all([
      mutate(),
      refreshLinkedTask(),
      mutateCache(SWR_KEYS.inboxWaitingTasks),
      invalidateNotificationCaches(),
    ]);
  };

  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-5xl flex-col gap-6 p-4 sm:p-8" data-testid="reviewed-tasks-page">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <ResponsiveLayout display="flex" className="flex-col gap-1">
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">{workspaceText("myDrafts")}</h1>
          <p className="text-sm text-text-03">{workspaceText("writeTheRequestStartItWhenReadyAndApprove")}</p>
        </ResponsiveLayout>
        {!creating && (
          <ActionButton type="button" className={primary} onClick={() => setCreating(true)}>{workspaceText("newDraft")}</ActionButton>
        )}
      </header>

      {creating && (
        <section className={card} aria-labelledby="new-task">
          <h2 id="new-task" className="mb-3 text-base font-semibold text-text-05">{workspaceText("newDraft")}</h2>
          <DraftForm
            task={null}
            onSaved={async (t) => {
              setCreating(false);
              setSelected(t.id);
              await mutate();
            }}
            onCancel={() => setCreating(false)}
          />
        </section>
      )}

      <ResponsiveLayout display="grid" className="grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-[18rem_minmax(0,1fr)]">
        <nav aria-label={workspaceText("yourDrafts")}>
          {isLoading ? (
            <p className="text-sm text-text-03">{workspaceText("loading")}</p>
          ) : error ? (
            <p role="alert" className="text-sm text-text-05">{workspaceText("draftsCouldNotBeLoaded")}</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-text-03">{workspaceText("noDraftsYet")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {tasks.map((t) => (
                <li key={t.id}>
                  <ActionButton
                    type="button"
                    onClick={() => setSelected(t.id)}
                    aria-current={t.id === selected ? "true" : undefined}
                    className={`flex min-h-11 w-full flex-col items-start rounded-xl border px-3 py-2 text-left ${t.id === selected ? "border-text-05 bg-background-neutral-01" : "border-border-01"}`}
                  >
                    <span className="w-full truncate text-sm font-semibold text-text-05">{t.title}</span>
                    <span className="text-xs text-text-03">{STATE_LABEL[t.state]}</span>
                  </ActionButton>
                </li>
              ))}
            </ul>
          )}
        </nav>
        <div>
          {current ? (
            <TaskDetail key={`${current.id}-${current.version}`} task={current} onChange={refreshTasks} />
          ) : selected ? (
            <p role={linkedError ? "alert" : "status"} className="text-sm text-text-03">
              {linkedError ? "This draft could not be opened." : "Loading draft…"}
            </p>
          ) : (
            tasks.length > 0 && <p className="text-sm text-text-03">{workspaceText("pickADraftToSeeIt")}</p>
          )}
        </div>
      </ResponsiveLayout>
    </ResponsiveLayout>
  );
}
