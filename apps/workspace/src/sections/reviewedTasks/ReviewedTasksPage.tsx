"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import TaskActions from "@/sections/reviewedTasks/TaskActions";

const URL = "/api/tasks";

type State = "draft" | "planning" | "plan_review" | "plan_accepted" | "plan_failed" | "running" | "draft_ready" | "run_failed" | "approved" | "cancelled";

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
};
const ROUTE_LABEL: Record<string, string> = { local: "Local", private: "Private", cloud: "Cloud" };

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

async function call(path: string, method: string, body: unknown): Promise<Task> {
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
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
        Title
        <input className={`${input} min-h-11`} value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
        What should the task do?
        <textarea className={input} rows={4} value={request} maxLength={8000} onChange={(e) => setRequest(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
        Desired output <span className="font-normal text-text-03">(optional)</span>
        <input className={`${input} min-h-11`} value={output} maxLength={8000} onChange={(e) => setOutput(e.target.value)} />
      </label>
      {error && <p role="alert" className="text-sm text-status-error-05">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="button" className={primary} disabled={busy || !title.trim() || !request.trim()} onClick={save}>
          {busy ? "Saving…" : "Save draft"}
        </button>
        {onCancel && (
          <button type="button" className={secondary} disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      <p className="text-xs text-text-03">Saving a draft runs nothing. Work begins only when you press Start.</p>
    </div>
  );
}

function TaskDetail({ task, onChange }: { task: Task; onChange: () => Promise<unknown> }) {
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

  const act = async (name: string, path: string, body: unknown) => {
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
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <h2 id="task-title" className="min-w-0 text-lg font-semibold text-text-05">{task.title}</h2>
        <span data-testid="task-state" className="rounded-full border border-border-01 px-2.5 py-0.5 text-xs font-medium text-text-03">
          {STATE_LABEL[task.state]}
        </span>
      </div>

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
          {task.desired_output && <p className="mt-2 text-sm text-text-03">Desired output: {task.desired_output}</p>}
          {task.revision_note && task.state === "draft" && (
            <p className="mt-3 rounded-xl bg-background-neutral-01 px-3 py-2 text-sm text-text-05">
              Your revision note: {task.revision_note}
            </p>
          )}
        </>
      )}

      {task.plan && task.state !== "draft" && (
        <section className="mt-4" aria-labelledby="plan-h">
          <h3 id="plan-h" className="mb-2 text-sm font-semibold text-text-05">
            Proposed plan
            {task.plan_route && (
              <span className="ml-2 font-normal text-text-03">drafted on the {ROUTE_LABEL[task.plan_route] ?? task.plan_route} route</span>
            )}
          </h3>
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
          <h3 id="draft-h" className="mb-2 text-sm font-semibold text-text-05">
            Draft
            <span className="ml-2 font-normal text-text-03" data-testid="draft-version">
              version {task.draft_version ?? 1}
              {latestBy === "owner"
                ? " · edited by you"
                : task.draft_route
                  ? ` · written on the ${ROUTE_LABEL[task.draft_route] ?? task.draft_route} route`
                  : ""}
            </span>
          </h3>
          {editingDraft ? (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
                Edit the draft. Cite only the numbered sources below, like [1].
                <textarea
                  className={input}
                  rows={6}
                  maxLength={20000}
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button
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
                </button>
                <button type="button" className={secondary} disabled={!!busy} onClick={() => setEditingDraft(false)}>
                  Cancel
                </button>
              </div>
            </div>
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
                      <span className="ml-2 inline-flex gap-1">
                        <button
                          type="button"
                          className="min-h-9 rounded-lg border border-border-02 px-3 text-xs font-semibold text-text-05 disabled:opacity-50"
                          disabled={!!busy}
                          onClick={() => act(`keep-${c.i}`, `/claims/${c.i}`, { version: task.version, decision: "keep" })}
                        >
                          Keep
                        </button>
                        <button
                          type="button"
                          className="min-h-9 rounded-lg border border-border-02 px-3 text-xs font-semibold text-text-05 disabled:opacity-50"
                          disabled={!!busy}
                          onClick={() => act(`remove-${c.i}`, `/claims/${c.i}`, { version: task.version, decision: "remove" })}
                        >
                          Remove
                        </button>
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="whitespace-pre-wrap text-sm text-text-05">{task.draft_text}</p>
          )}
          {task.draft_sources && task.draft_sources.length > 0 ? (
            <ol className="mt-3 space-y-1 text-xs text-text-03" aria-label="Sources" data-testid="task-sources">
              {task.draft_sources.map((src) => (
                <li key={src.n}>
                  [{src.n}]{" "}
                  {src.link ? (
                    <a className="underline" href={src.link} target="_blank" rel="noreferrer">{src.title}</a>
                  ) : (
                    src.title
                  )}
                  {!src.cited && <span className="ml-1">(found but not cited)</span>}
                  {src.flagged && (
                    <span className="ml-2 text-status-warning-05" data-testid="source-flagged">
                      contains text that reads like an instruction to the model
                    </span>
                  )}
                  {src.passage && (
                    <details className="mt-1">
                      <summary className="cursor-pointer">Passage the model saw</summary>
                      <p className="mt-1 whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1">{src.passage}</p>
                    </details>
                  )}
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-xs text-text-03">No permitted source was found for this request.</p>
          )}
          <p className="mt-3 text-xs text-text-03">
            {task.state === "approved"
              ? `You approved exactly this draft${task.approved_at ? ` on ${new Date(task.approved_at).toLocaleString()}` : ""}. Export checks your access to each cited source again.`
              : "Only sources you can open were used. Approving covers exactly this draft; a new run needs a new approval."}
          </p>
          {task.state === "draft_ready" && !editingDraft && !task.withheld && (
            <button
              type="button"
              className={`${secondary} mt-3`}
              disabled={!!busy}
              onClick={() => {
                setDraftText(task.draft_text ?? "");
                setEditingDraft(true);
              }}
            >
              Edit draft
            </button>
          )}
          {task.draft_versions && task.draft_versions.length > 1 && (
            <details className="mt-3 text-xs text-text-03" data-testid="draft-history">
              <summary className="cursor-pointer">Previous versions ({task.draft_versions.length - 1})</summary>
              <ol className="mt-2 space-y-2">
                {task.draft_versions.slice(0, -1).reverse().map((v) => (
                  <li key={v.v} className="rounded-lg border border-border-01 px-3 py-2">
                    <div className="font-medium text-text-05">
                      Version {v.v} · {v.by === "owner" ? "edited by you" : "written by the model"} · {new Date(v.at).toLocaleString()}
                    </div>
                    <p className="mt-1 whitespace-pre-wrap">{v.text}</p>
                  </li>
                ))}
              </ol>
            </details>
          )}
          {task.exported_at && (
            <p className="mt-1 text-xs text-text-03" data-testid="task-exported">
              Last exported {new Date(task.exported_at).toLocaleString()}.
            </p>
          )}
        </section>
      )}
      {task.state === "run_failed" && task.run_error && (
        <p role="alert" className="mt-4 text-sm text-status-error-05">{task.run_error}</p>
      )}
      {task.state === "plan_failed" && task.plan_error && (
        <p role="alert" className="mt-4 text-sm text-status-error-05">{task.plan_error}</p>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-status-error-05">{error}</p>}

      {!editing && (
        <div className="mt-4 flex flex-wrap gap-2">
          {task.state === "draft" && (
            <>
              <button type="button" className={primary} disabled={!!busy} onClick={() => act("start", "/start", { version: task.version })}>
                {busy === "start" ? "Drafting a plan…" : "Start"}
              </button>
              <button type="button" className={secondary} disabled={!!busy} onClick={() => setEditing(true)}>
                Edit
              </button>
            </>
          )}
          {task.state === "plan_review" && (
            <button type="button" className={primary} disabled={!!busy} onClick={() => act("accept", "/plan/accept", { version: task.version })}>
              {busy === "accept" ? "Accepting…" : "Accept plan"}
            </button>
          )}
          {(task.state === "plan_review" || task.state === "plan_failed") && (
            <div className="flex w-full flex-wrap items-end gap-2">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-text-05">
                What should change?
                <input className={`${input} min-h-11`} value={note} maxLength={8000} onChange={(e) => setNote(e.target.value)} />
              </label>
              <button type="button" className={secondary} disabled={!!busy} onClick={() => act("revise", "/plan/revise", { version: task.version, note })}>
                Revise
              </button>
            </div>
          )}
          {(task.rule_results ?? []).length > 0 && (
            <ul className="w-full text-sm" data-testid="rule-results" aria-label="Pack review rules">
              {(task.rule_results ?? []).map((r, i) => (
                <li key={i} className={r.passed ? "text-text-03" : r.severity === "block" ? "text-status-error-05" : "text-status-warning-05"}>
                  {r.passed ? "Met" : r.severity === "block" ? "Not met (must be fixed to approve)" : "Warning"}: {r.message} <span className="text-xs">({r.detail})</span>
                </li>
              ))}
            </ul>
          )}
          {task.state === "draft_ready" && task.draft_hash && !task.withheld && (
            <button
              type="button"
              className={primary}
              disabled={!!busy || openClaims > 0 || (task.rule_results ?? []).some((r) => !r.passed && r.severity === "block")}
              title={openClaims > 0 ? `Decide on ${openClaims} unsupported claim(s) first` : (task.rule_results ?? []).some((r) => !r.passed && r.severity === "block") ? "The pack's review rules are not met" : undefined}
              onClick={() => act("approve", "/approve", { version: task.version, draft_hash: task.draft_hash })}
            >
              {busy === "approve" ? "Approving…" : openClaims > 0 ? `Approve (${openClaims} claim${openClaims === 1 ? "" : "s"} to decide)` : "Approve this draft"}
            </button>
          )}
          {task.state === "approved" && (
            <button type="button" className={primary} disabled={!!busy} onClick={exportDraft}>
              {busy === "export" ? "Checking access…" : "Export as Markdown"}
            </button>
          )}
          {task.state === "draft_ready" && (
            <div className="flex w-full flex-wrap items-end gap-2">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-text-05">
                What should change?
                <input className={`${input} min-h-11`} value={note} maxLength={8000} onChange={(e) => setNote(e.target.value)} />
              </label>
              <button type="button" className={secondary} disabled={!!busy} onClick={() => act("revise", "/plan/revise", { version: task.version, note })}>
                Revise
              </button>
            </div>
          )}
          {(task.state === "plan_accepted" || task.state === "run_failed") && (
            <button type="button" className={primary} disabled={!!busy} onClick={() => act("run", "/run", { version: task.version })}>
              {busy === "run" ? "Gathering sources and drafting…" : task.state === "run_failed" ? "Try again" : "Run plan"}
            </button>
          )}
          {(task.state === "draft" || task.state === "plan_review" || task.state === "plan_failed" || task.state === "plan_accepted" || task.state === "run_failed" || task.state === "draft_ready") && (
            <button type="button" className={`${secondary} ml-auto`} disabled={!!busy} onClick={() => act("cancel", "/cancel", { version: task.version })}>
              Cancel task
            </button>
          )}
        </div>
      )}
      {task.state === "approved" && !task.withheld && <TaskActions taskId={task.id} />}
      {task.state === "plan_accepted" && (
        <p className="mt-4 text-sm text-text-03">
          Plan accepted. Run it to gather sources you can open and write a cited draft.
        </p>
      )}
    </article>
  );
}

/**
 * Reviewed tasks: write a draft, start it on purpose, review the proposed plan,
 * then accept, revise or cancel. Nothing runs before Start, and the plan is
 * drafted only on a route the administrator's policy allows.
 */
export default function ReviewedTasksPage() {
  const { data, error, isLoading, mutate } = useSWR<Task[]>(URL, errorHandlingFetcher);
  const params = useSearchParams();
  const [selected, setSelected] = useState<string | null>(params.get("task"));
  const [creating, setCreating] = useState(false);
  const tasks = data ?? [];
  const current = tasks.find((t) => t.id === selected) ?? null;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-8" data-testid="reviewed-tasks-page">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Reviewed tasks</h1>
          <p className="text-sm text-text-03">Write the request, start it when ready, and approve the plan before any work runs.</p>
        </div>
        {!creating && (
          <button type="button" className={primary} onClick={() => setCreating(true)}>
            New task
          </button>
        )}
      </header>

      {creating && (
        <section className={card} aria-labelledby="new-task">
          <h2 id="new-task" className="mb-3 text-base font-semibold text-text-05">New task</h2>
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

      <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
        <nav aria-label="Your tasks">
          {isLoading ? (
            <p className="text-sm text-text-03">Loading…</p>
          ) : error ? (
            <p role="alert" className="text-sm text-text-05">Tasks could not be loaded.</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-text-03">No tasks yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {tasks.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(t.id)}
                    aria-current={t.id === selected ? "true" : undefined}
                    className={`flex min-h-11 w-full flex-col items-start rounded-xl border px-3 py-2 text-left ${t.id === selected ? "border-text-05 bg-background-neutral-01" : "border-border-01"}`}
                  >
                    <span className="w-full truncate text-sm font-semibold text-text-05">{t.title}</span>
                    <span className="text-xs text-text-03">{STATE_LABEL[t.state]}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>
        <div>
          {current ? (
            <TaskDetail key={`${current.id}-${current.version}`} task={current} onChange={() => mutate()} />
          ) : (
            tasks.length > 0 && <p className="text-sm text-text-03">Pick a task to see it.</p>
          )}
        </div>
      </div>
    </div>
  );
}
