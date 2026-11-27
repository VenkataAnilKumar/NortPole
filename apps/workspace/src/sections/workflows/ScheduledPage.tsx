"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeSelect, NativeTextArea } from "@opal/components";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "@opal/navigation";
import { Tabs } from "@opal/components";
import { SvgClock } from "@opal/icons";
import useSWR from "swr";
import { useDocumentSets } from "@/app/admin/documents/sets/hooks";
import { errorHandlingFetcher } from "@/lib/fetcher";
import ScheduledExpenseInputs, { type ExpenseInputs } from "./ScheduledExpenseInputs";

interface Run {
  id: string; fired_at: string; outcome: string; reason: string | null; task_id: string | null; task_state: string | null;
  route_kind: string | null; input_tokens: number; output_tokens: number;
  chat_session_id: string | null;
}
interface RunNotifications {
  notify_plan_ready: boolean;
  notify_needs_review: boolean;
  notify_run_failed: boolean;
  notify_run_complete: boolean;
}
interface Schedule extends RunNotifications {
  id: string; name: string; title: string; pack_id: string | null; pack_template: string | null; cadence: string; at_time: string;
  timezone: string; weekday: number | null; month_day: number | null; run_on: string | null; when: string; next_run_at: string | null;
  state: string; pause_reason: string | null; pause_text: string | null; unaccepted_streak: number; last_run: Run | null;
  shared_with_groups: string[]; copied_from_id: string | null; version: number;
  expense_review: ExpenseInputs | null;
  source_library_id: number | null;
}
interface Mine { schedules: Schedule[]; scheduling_allowed: boolean; source_events_allowed: boolean; max_per_person: number; my_groups: string[] }
interface Shared { id: string; name: string; owner_email: string; when: string; title: string; request: string; desired_output: string; already_copied: boolean }
interface Template { id: string; title: string }
interface Pack { pack_id: string; name: string; templates: Template[]; ready_on_current_route: boolean }
interface Draft { id: string; title: string }

type ScheduleRequest = Partial<RunNotifications> & {
  version?: number;
  groups?: string[];
  name?: string;
  cadence?: string;
  at_time?: string;
  timezone?: string;
  weekday?: number | null;
  month_day?: number | null;
  run_on?: string | null;
  source_library_id?: number | null;
  expense_review?: ExpenseInputs;
  task_id?: string;
  pack_id?: string;
  pack_template?: string;
  title?: string;
  request?: string;
  prepare_now?: boolean;
};

const URL = "/api/workflow-schedules";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const OUTCOME: Record<string, string> = {
  queued: "Queued", running: "Running", interrupted: "Result unavailable", expired: "Expired", failed: "Failed",
  plan_ready: "Plan drafted", plan_failed: "Plan could not be drafted", skipped: "Skipped", paused: "Paused",
  review_complete: "Review complete", needs_review: "Needs review",
  no_new_csv: "Skipped", drive_skipped: "Skipped",
};
const TASK: Record<string, string> = {
  plan_review: "waiting for you", plan_accepted: "accepted", running: "running", draft_ready: "draft ready",
  run_failed: "run failed", approved: "approved", superseded: "replaced by a newer run", cancelled: "cancelled",
  plan_failed: "no plan", draft: "sent back to edit",
};

async function call(url: string, method: string, body?: ScheduleRequest): Promise<any> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* not json */ }
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  return data;
}

function when(iso: string | null): string {
  if (!iso) return "not scheduled";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "not scheduled" : d.toLocaleString();
}

interface FormValue extends RunNotifications {
  name: string; cadence: string; at_time: string; timezone: string; weekday: number; month_day: number; run_on: string;
  source: "template" | "draft" | "own" | "expense"; pack: string; title: string; request: string;
  expense: ExpenseInputs;
  sourceLibrary: number;
}

function blank(): FormValue {
  let tz = "UTC";
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { /* keep UTC */ }
  return { name: "", notify_plan_ready: false, notify_needs_review: true, notify_run_failed: true, notify_run_complete: false,
    cadence: "weekdays", at_time: "08:30", timezone: tz, weekday: 0, month_day: 1, run_on: "", source: "own", pack: "", title: "", request: "",
    sourceLibrary: 0,
    expense: { library_id: 0, csv_file_id: null, drive_source: null, policy_title: "" } };
}

function schedulePreview(value: FormValue) {
  if (value.cadence === "source") return "A new plan is prepared when an indexed document changes in this library.";
  if (!value.at_time || !value.timezone.trim() || (value.cadence === "once" && !value.run_on)) {
    return "Choose a date or recurrence, time, and time zone.";
  }
  const time = new Intl.DateTimeFormat(undefined, { timeStyle: "short", timeZone: "UTC" })
    .format(new Date(`2000-01-01T${value.at_time}:00Z`));
  const frequency = value.cadence === "once" ? `Once on ${value.run_on}`
    : value.cadence === "weekly" ? `Every ${DAYS[value.weekday]}`
    : value.cadence === "monthly" ? `Monthly on day ${value.month_day}`
    : value.cadence === "daily" ? "Every day" : "Weekdays";
  return `${frequency} at ${time} (${value.timezone.trim()})`;
}

/** Create a schedule or update its timing and saved review inputs. */
function ScheduleForm({ initial, editing, packs, draft, sourceEventsAllowed, onDone, onCancel }: {
  sourceEventsAllowed: boolean; initial: FormValue; editing: Schedule | null; packs: Pack[]; draft: Draft | null; onDone: (msg: string, planStatus?: "ready" | "failed") => void; onCancel: () => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [v, setV] = useState<FormValue>(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const isSource = v.cadence === "source";
  const libraries = useDocumentSets(false, isSource);
  const set = (patch: Partial<FormValue>) => setV((current) => {
    const cadence = current.cadence === "source" && patch.source && patch.source !== "own"
      ? "weekdays"
      : current.cadence;
    return { ...current, cadence, ...patch };
  });
  const isExpense = editing ? Boolean(editing.expense_review) : v.source === "expense";
  const notificationOptions: [keyof RunNotifications, string][] = [
    isExpense ? ["notify_needs_review", "A result needs review"] : ["notify_plan_ready", "A plan is ready"],
    ["notify_run_failed", "A run fails"],
    ["notify_run_complete", "A run finishes successfully"],
  ];
  const options = packs.filter((p) => p.ready_on_current_route).flatMap((p) => p.templates.map((t) => ({ key: `${p.pack_id}/${t.id}`, label: `${p.name}: ${t.title}` })));

  const submit = async (prepareNow: boolean) => {
    setBusy(true);
    setErr(null);
    try {
      const timing = {
        cadence: v.cadence, at_time: isSource ? "00:00" : v.at_time, timezone: isSource ? "UTC" : v.timezone.trim(),
        source_library_id: isSource ? v.sourceLibrary : null, notify_plan_ready: v.notify_plan_ready,
        notify_needs_review: v.notify_needs_review, notify_run_failed: v.notify_run_failed, notify_run_complete: v.notify_run_complete,
        weekday: v.cadence === "weekly" ? v.weekday : null, month_day: v.cadence === "monthly" ? v.month_day : null,
        run_on: v.cadence === "once" ? v.run_on || null : null,
      };
      if (editing) {
        const body: ScheduleRequest = { version: editing.version, name: v.name, ...timing };
        if (isExpense) body.expense_review = v.expense;
        await call(`${URL}/${editing.id}`, "PATCH", body);
        onDone(`Saved "${v.name}".`);
      } else {
        const what = v.source === "draft" && draft ? { task_id: draft.id }
          : v.source === "template" ? { pack_id: v.pack.split("/")[0], pack_template: v.pack.split("/")[1] }
          : isExpense ? { expense_review: v.expense }
          : { title: v.title, request: v.request };
        const saved: Schedule & { initial_plan: Run | null } = await call(URL, "POST", {
          name: v.name, ...timing, ...what, prepare_now: prepareNow,
        });
        if (!prepareNow) onDone(isSource ? `Watching Knowledge for "${saved.name}".` : `Scheduled "${saved.name}".`);
        else if (isExpense) {
          const outcome = saved.initial_plan?.outcome;
          if (outcome === "review_complete" || outcome === "needs_review") {
            onDone(`Scheduled "${saved.name}". First run: ${OUTCOME[outcome]}.`);
          } else if (outcome === "no_new_csv") {
            onDone(`Scheduled "${saved.name}". ${saved.initial_plan?.reason ?? "No new CSV was found."}`);
          } else {
            onDone(`Scheduled "${saved.name}", but the first review could not finish. ${saved.initial_plan?.reason ?? "Check the schedule history for details."}`, "failed");
          }
        }
        else if (saved.initial_plan?.outcome === "plan_ready") {
          onDone(`Scheduled "${saved.name}". The first plan is ready for review.`, "ready");
        } else {
          const reason = saved.initial_plan?.reason ?? "Check the schedule history for details.";
          onDone(`Scheduled "${saved.name}", but the first plan could not be prepared. ${reason}`, "failed");
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "The schedule could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const drive = v.expense.drive_source;
  const validCsv = drive
    ? drive.app_id > 0 && /^[A-Za-z0-9_-]{1,128}$/.test(drive.folder_id) && !!drive.filename_pattern.trim()
    : !!v.expense.csv_file_id;
  const timingReady = isSource
    ? sourceEventsAllowed && libraries.data?.some((library) => library.id === v.sourceLibrary)
    : v.at_time && v.timezone.trim();
  const ready = v.name.trim() && timingReady &&
    (isExpense ? v.expense.library_id && validCsv : editing || (v.source === "draft" ? !!draft : v.source === "template" ? !!v.pack : v.title.trim() && v.request.trim()))
    && (v.cadence !== "once" || v.run_on);
  return (
    <section className={card} aria-labelledby="sched-form" data-testid="schedule-form">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border-01 pb-4">
        <div>
          <h2 id="sched-form" className="font-[family-name:var(--font-serif)] text-2xl text-text-05">{editing ? `Change "${editing.name}"` : "New schedule"}</h2>
          <p className="mt-1 text-sm text-text-03">{isExpense ? "Expense Review results appear in Workflows → Runs." : "Plans go to your Inbox for approval before work begins."}</p>
        </div>
        <ResponsiveLayout display="flex" className="flex-wrap gap-2">
          <ActionButton type="button" className={secondary} disabled={busy} onClick={onCancel}>{workspaceText("cancel")}</ActionButton>
          {!editing && !isSource && <ActionButton type="button" className={secondary} disabled={busy || !ready} onClick={() => void submit(true)}>{isExpense ? "Save and run now" : "Save and prepare a plan now"}</ActionButton>}
          <ActionButton type="button" className={primary} disabled={busy || !ready} onClick={() => void submit(false)}>{busy ? "Saving…" : "Save schedule"}</ActionButton>
        </ResponsiveLayout>
      </header>
      {err && <p role="alert" className="mt-3 text-sm text-status-text-error-05">{err}</p>}
      <section aria-labelledby="schedule-task" className="py-4">
        <h3 id="schedule-task" className="mb-3 font-semibold text-text-05">{workspaceText("task")}</h3>
        <ResponsiveLayout display="grid" className="gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05 sm:col-span-2">{workspaceText("name")}<NativeInput className={input} value={v.name} maxLength={200} onChange={(e) => set({ name: e.target.value })} placeholder={workspaceText("forExampleMondayPolicyCheck")} />
        </label>
        {!editing && (
          <fieldset className="flex flex-col gap-2 sm:col-span-2">
            <legend className="mb-1 text-sm font-medium text-text-05">{workspaceText("whatRuns")}</legend>
            {draft && (
              <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
                <NativeInput type="radio" name="source" checked={v.source === "draft"} onChange={() => set({ source: "draft" })} />{workspaceText("yourDraft")}{" "}{draft.title || "Untitled draft"}
              </label>
            )}
            <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
              <NativeInput type="radio" name="source" checked={v.source === "expense"} onChange={() => set({ source: "expense" })} />{workspaceText("expenseReview")}</label>
            <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
              <NativeInput type="radio" name="source" checked={v.source === "template"} onChange={() => set({ source: "template" })} />{workspaceText("aWorkflow")}</label>
            {v.source === "template" && (
              <label className="flex flex-col gap-1 text-sm text-text-04">
                <span className="sr-only">{workspaceText("workflow")}</span>
                <NativeSelect className={input} value={v.pack} onChange={(e) => set({ pack: e.target.value })}>
                  <option value="">{workspaceText("chooseAWorkflow")}</option>
                  {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                </NativeSelect>
              </label>
            )}
            <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
              <NativeInput type="radio" name="source" checked={v.source === "own"} onChange={() => set({ source: "own" })} />{workspaceText("yourOwnRequest")}</label>
            {v.source === "own" && (
              <ResponsiveLayout display="flex" className="flex-col gap-2">
                <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("title")}<NativeInput className={input} value={v.title} maxLength={300} onChange={(e) => set({ title: e.target.value })} />
                </label>
                <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("request")}<NativeTextArea className={`${input} min-h-24 py-2`} value={v.request} maxLength={8000} onChange={(e) => set({ request: e.target.value })} />
                </label>
              </ResponsiveLayout>
            )}
          </fieldset>
        )}
        {isExpense && (
          <div className="sm:col-span-2">
            <ScheduledExpenseInputs value={v.expense} inputClass={input}
              onChange={(patch) => setV((current) => ({ ...current, expense: { ...current.expense, ...patch } }))} />
          </div>
        )}
        </ResponsiveLayout>
      </section>
      <section aria-labelledby="schedule-timing" className="border-y border-border-01 py-4">
        <h3 id="schedule-timing" className="mb-3 font-semibold text-text-05">{workspaceText("schedule")}</h3>
        <ResponsiveLayout display="grid" className="gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("starts")}<NativeSelect className={input} value={v.cadence} disabled={editing?.cadence === "source"} onChange={(e) => set({ cadence: e.target.value })}>
            {(editing?.cadence === "source" || (!editing && sourceEventsAllowed && v.source === "own")) && (
              <option value="source">{workspaceText("whenADocumentChangesInKnowledge")}</option>
            )}
            {editing?.cadence !== "source" && <>
            <option value="once">{workspaceText("once")}</option>
            <option value="daily">{workspaceText("everyDay")}</option>
            <option value="weekdays">{workspaceText("weekdays")}</option>
            <option value="weekly">{workspaceText("onceAWeek")}</option>
            <option value="monthly">{workspaceText("onceAMonth")}</option>
            </>}
          </NativeSelect>
        </label>
        {v.cadence === "weekly" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("day")}<NativeSelect className={input} value={v.weekday} onChange={(e) => set({ weekday: Number(e.target.value) })}>
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </NativeSelect>
          </label>
        )}
        {v.cadence === "monthly" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("dayOfTheMonth1To28")}<NativeInput className={input} type="number" min={1} max={28} value={v.month_day} onChange={(e) => set({ month_day: Number(e.target.value) })} />
          </label>
        )}
        {v.cadence === "once" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("date")}<NativeInput className={input} type="date" value={v.run_on} onChange={(e) => set({ run_on: e.target.value })} />
          </label>
        )}
        {isSource ? (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("knowledgeLibrary")}<NativeSelect className={input} value={v.sourceLibrary} onChange={(e) => set({ sourceLibrary: Number(e.target.value) })}>
              <option value={0}>{workspaceText("chooseALibrary")}</option>
              {libraries.data?.map((library) => <option key={library.id} value={library.id}>{library.name}</option>)}
            </NativeSelect>
            {libraries.error && <span role="alert">{workspaceText("knowledgeLibrariesCouldNotBeLoaded")}</span>}
            {libraries.data?.length === 0 && <span>{workspaceText("noKnowledgeLibrariesAreAvailableToThisAccount")}</span>}
          </label>
        ) : (
          <>
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("time")}<NativeInput className={input} type="time" value={v.at_time} onChange={(e) => set({ at_time: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("timeZone")}<NativeInput className={input} value={v.timezone} maxLength={64} onChange={(e) => set({ timezone: e.target.value })} />
        </label>
          </>
        )}
        </ResponsiveLayout>
        <p role="status" aria-label={workspaceText("schedulePreview")} className="mt-4 flex items-center gap-2 rounded-lg bg-background-neutral-02 px-3 py-2 text-sm text-text-05">
          <SvgClock size={16} className="shrink-0" />
          {schedulePreview(v)}
        </p>
      </section>
      <details className="mt-4 rounded-xl border border-border-01 px-4 py-3">
        <summary className="cursor-pointer font-semibold text-text-05">{workspaceText("advancedSettings")}</summary>
        <div className="mt-3">
          <Tabs defaultValue="general">
            <Tabs.List aria-label={workspaceText("advancedSettings")}>
              <Tabs.Trigger value="general">{workspaceText("general")}</Tabs.Trigger>
              <Tabs.Trigger value="notifications">{workspaceText("notifications")}</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="general">
              <p className="mt-3 text-sm text-text-03">{isExpense
                ? "The workspace runs the review using your access to the selected sources."
                : "The workspace prepares a plan using your Knowledge permissions. The plan appears in Inbox for approval."}</p>
            </Tabs.Content>
            <Tabs.Content value="notifications">
              <fieldset className="mt-3 flex flex-col gap-2 text-sm text-text-05">
                <legend className="mb-2 text-text-03">{workspaceText("sendAnInboxAlertWhen")}</legend>
                {notificationOptions.map(([field, label]) => (
                  <label key={field} className="flex min-h-8 items-center gap-2">
                    <NativeInput type="checkbox" checked={v[field]} onChange={(event) => set({ [field]: event.target.checked })} />
                    {label}
                  </label>
                ))}
              </fieldset>
            </Tabs.Content>
          </Tabs>
        </div>
      </details>
    </section>
  );
}

function History({ id, focusRun }: { id: string; focusRun?: string | null }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, error } = useSWR<Run[]>(`${URL}/${id}/runs${focusRun ? `?include=${encodeURIComponent(focusRun)}` : ""}`, errorHandlingFetcher);
  const focused = data?.some((run) => run.id === focusRun);
  useEffect(() => {
    if (focused) document.getElementById(`workflow-run-${focusRun}`)?.focus();
  }, [focused, focusRun]);
  if (error) return <p className="mt-2 text-sm text-status-text-error-05">{workspaceText("theHistoryCouldNotBeLoaded")}</p>;
  if (!data) return <p className="mt-2 text-sm text-text-03">{workspaceText("loading")}</p>;
  if (!data.length) return <p className="mt-2 text-sm text-text-03">{workspaceText("noRunsYet")}</p>;
  return (
    <ol className="mt-2 flex flex-col divide-y divide-border-01" aria-label={workspaceText("runsNewestFirst")} data-testid="schedule-history">
      {data.map((r) => (
        <li key={r.id} id={`workflow-run-${r.id}`} tabIndex={r.id === focusRun ? -1 : undefined}
          className="flex flex-wrap items-baseline justify-between gap-2 py-2 text-sm focus-visible:outline">
          <span className="min-w-0 text-text-05">
            {when(r.fired_at)}: {OUTCOME[r.outcome] ?? r.outcome}
            {r.task_state && <> → {TASK[r.task_state] ?? r.task_state}</>}
            {r.reason && <span className="block text-xs text-text-03">{r.reason}</span>}
            {r.route_kind && <span className="block text-xs text-text-03">{workspaceText("plannedOnThe")}{" "}{r.route_kind}{" "}{workspaceText("route")}{" "}{r.input_tokens + r.output_tokens} tokens</span>}
          </span>
          {r.task_id && <NavLink href={`/app/workflows/drafts?task=${encodeURIComponent(r.task_id)}`} className="text-sm font-semibold text-text-05 underline">{workspaceText("openTheDraft")}</NavLink>}
          {r.chat_session_id && <NavLink href={`/app?chatId=${encodeURIComponent(r.chat_session_id)}`} className="text-sm font-semibold text-text-05 underline">{workspaceText("openChat")}</NavLink>}
        </li>
      ))}
    </ol>
  );
}

/**
 * Manage scheduled plans and private Expense Reviews. Plans wait in Inbox for approval.
 */
export default function ScheduledPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const params = useSearchParams();
  const { data, error, isLoading, mutate } = useSWR<Mine>(URL, errorHandlingFetcher);
  const targetedSchedule = params?.get("schedule") ?? null;
  const targetedRun = params?.get("run");
  const { data: shared, mutate: mutateShared } = useSWR<Shared[]>(
    `${URL}/shared${targetedSchedule ? `?include=${encodeURIComponent(targetedSchedule)}` : ""}`,
    errorHandlingFetcher
  );
  const { data: packs } = useSWR<Pack[]>("/api/packs", errorHandlingFetcher);
  const taskId = params?.get("task");
  const { data: draft } = useSWR<Draft>(taskId ? `/api/tasks/${encodeURIComponent(taskId)}` : null, errorHandlingFetcher);
  const [form, setForm] = useState<{ initial: FormValue; editing: Schedule | null } | null>(null);
  const [history, setHistory] = useState<string | null>(targetedSchedule);
  const [manualRun, setManualRun] = useState<{ scheduleId: string; runId: string } | null>(null);
  useEffect(() => {
    setHistory(targetedSchedule);
    setManualRun(null);
  }, [targetedSchedule, targetedRun]);
  const [sharing, setSharing] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string; inbox?: boolean; runId?: string } | null>(null);

  // Arriving from a workflow's or a draft's "Schedule" button opens the form for it.
  const preset = useMemo(() => {
    const pack = params?.get("pack"), template = params?.get("template");
    if (pack && template) return { ...blank(), source: "template" as const, pack: `${pack}/${template}` };
    if (taskId) return { ...blank(), source: "draft" as const };
    if (params?.get("new") === "1") return blank();
    return null;
  }, [params, taskId]);
  useEffect(() => {
    if (preset && !form) setForm({ initial: preset, editing: null });
  }, [preset]);

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
      await Promise.all([mutate(), mutateShared()]);
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." });
    } finally {
      setBusy(false);
    }
  }

  const runNow = async (schedule: Schedule) => {
    setBusy(true);
    setMsg(null);
    try {
      const result: Run = await call(`${URL}/${schedule.id}/run-now`, "POST", { version: schedule.version });
      setManualRun({ scheduleId: schedule.id, runId: result.id });
      setHistory(schedule.id);
      const ok = ["plan_ready", "review_complete", "needs_review", "no_new_csv"].includes(result.outcome);
      const label = OUTCOME[result.outcome] ?? result.outcome;
      setMsg({ ok, text: result.reason ? `${label}. ${result.reason}` : label, runId: result.id });
      void mutate();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The run could not be started." });
    } finally {
      setBusy(false);
    }
  };

  const schedules = data?.schedules ?? [];
  const ownsTarget = data?.schedules.some((schedule) => schedule.id === targetedSchedule);
  const targetShared = shared?.some((schedule) => schedule.id === targetedSchedule);
  useEffect(() => {
    if (targetedSchedule && !targetedRun && (ownsTarget || targetShared)) {
      document.getElementById(`workflow-schedule-${targetedSchedule}`)?.focus();
    }
  }, [ownsTarget, targetShared, targetedSchedule, targetedRun]);
  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-5xl flex-col gap-6 p-4 sm:p-8" data-testid="scheduled-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">{workspaceText("scheduled")}</h1>
        <p className="text-sm text-text-03">{workspaceText("scheduledExpenseReviewsAppearInRunsOtherWorkflowsPrepare")}</p>
      </header>
      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="scheduled-message">
          {msg.text}
          {msg.inbox && <> <NavLink href="/app/inbox" className="font-semibold underline">{workspaceText("openInbox")}</NavLink></>}
          {msg.runId && <> <NavLink href={`/app/workflows/runs?run=${encodeURIComponent(msg.runId)}`} className="font-semibold underline">{workspaceText("viewInRuns")}</NavLink></>}
        </p>
      )}
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loading")}</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("scheduledWorkflowsCouldNotBeLoadedTryAgainIn")}</p>}
      {data && !data.scheduling_allowed && (
        <section className={card} data-testid="scheduling-off">
          <h2 className="text-base font-semibold text-text-05">{workspaceText("schedulingIsNotTurnedOnForYou")}</h2>
          <p className="mt-1 text-sm text-text-03">{workspaceText("anAdministratorDecidesWhoMayScheduleWorkflowsYourExisting")}</p>
        </section>
      )}
      {data && data.scheduling_allowed && !form && (
        <div>
          <ActionButton type="button" className={primary} onClick={() => { setMsg(null); setForm({ initial: blank(), editing: null }); }}>{workspaceText("newSchedule")}</ActionButton>
          <p className="mt-1 text-xs text-text-03">{schedules.filter((s) => s.state !== "ended").length} of {data.max_per_person}{" "}{workspaceText("schedulesInUse")}</p>
        </div>
      )}
      {form && (form.editing || data?.scheduling_allowed) && (
        <ScheduleForm
          key={form.editing?.id ?? "new"}
          initial={form.initial}
          editing={form.editing}
          packs={packs ?? []}
          draft={draft ?? null}
          sourceEventsAllowed={data?.source_events_allowed ?? false}
          onDone={(text, planStatus) => { setForm(null); setMsg({ ok: planStatus !== "failed", text, inbox: planStatus === "ready" }); void mutate(); }}
          onCancel={() => setForm(null)}
        />
      )}

      {data && (
        <section aria-labelledby="sched-mine" className="flex flex-col gap-3">
          <h2 id="sched-mine" className="text-xl font-semibold text-text-05">{workspaceText("yourSchedules")}</h2>
          {targetedSchedule && !ownsTarget && shared && !targetShared && (
            <p role="status" className="text-sm text-text-03">{workspaceText("thisScheduleIsNoLongerAvailable")}</p>
          )}
          {schedules.length === 0 ? (
            <p className="text-sm text-text-03">{workspaceText("noSchedulesYetUseScheduleOnAWorkflowOr")}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {schedules.map((s) => (
                <li key={s.id} id={`workflow-schedule-${s.id}`} tabIndex={s.id === targetedSchedule ? -1 : undefined}
                    className={`${card} focus-visible:outline`} data-testid="schedule-card">
                  <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-text-05">{s.name}</h3>
                      <p className="text-sm text-text-03">{s.when}</p>
                    </div>
                    <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04" data-testid="schedule-state">
                      {s.state === "active" ? "Active" : s.state === "paused" ? "Paused" : "Finished"}
                    </span>
                  </ResponsiveLayout>
                  {s.pause_text && <p className="mt-2 rounded-xl bg-status-warning-01 px-3 py-2 text-sm text-text-05">{s.pause_text}</p>}
                  <dl className="mt-3 grid gap-1 text-sm text-text-03 sm:grid-cols-2">
                    <div><dt className="inline font-medium text-text-05">{workspaceText("nextRun")}{" "}</dt><dd className="inline">{s.state === "active" ? s.cadence === "source"
                        ? data.source_events_allowed ? "On a Knowledge change" : "Knowledge triggers off"
                        : when(s.next_run_at) : "none"}</dd></div>
                    <div><dt className="inline font-medium text-text-05">{workspaceText("lastRun")}{" "}</dt><dd className="inline">{s.last_run ? `${OUTCOME[s.last_run.outcome] ?? s.last_run.outcome}, ${when(s.last_run.fired_at)}` : "none yet"}</dd></div>
                    <div className="sm:col-span-2"><dt className="inline font-medium text-text-05">{workspaceText("runs")}{" "}</dt><dd className="inline">{s.title}{s.shared_with_groups.length ? ` · shared with ${s.shared_with_groups.join(", ")}` : ""}{s.copied_from_id ? " · a copy of a shared schedule" : ""}</dd></div>
                  </dl>
                  <ResponsiveLayout display="flex" className="mt-3 flex-wrap gap-2">
                    {s.state === "active" && data.scheduling_allowed && s.cadence !== "source" && (
                      <ActionButton type="button" className={secondary} disabled={busy} onClick={() => void runNow(s)}>{workspaceText("runNow")}</ActionButton>
                    )}
                    {s.state === "active" && (
                      <ActionButton type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await call(`${URL}/${s.id}/pause`, "POST", { version: s.version }); return `Paused "${s.name}".`; })}>{workspaceText("pause")}</ActionButton>
                    )}
                    {s.state === "paused" && data.scheduling_allowed && (s.cadence !== "source" || data.source_events_allowed) && (
                      <ActionButton type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await call(`${URL}/${s.id}/resume`, "POST", { version: s.version }); return `Resumed "${s.name}".`; })}>{workspaceText("resume")}</ActionButton>
                    )}
                    {s.state !== "ended" && (
                      <ActionButton type="button" className={secondary} disabled={busy} onClick={() => {
                        setMsg(null);
                        const initial = blank();
                        setForm({ editing: s, initial: {
                          ...initial, name: s.name, notify_plan_ready: s.notify_plan_ready,
                          notify_needs_review: s.notify_needs_review, notify_run_failed: s.notify_run_failed,
                          notify_run_complete: s.notify_run_complete, cadence: s.cadence, at_time: s.at_time,
                          timezone: s.timezone, weekday: s.weekday ?? 0, month_day: s.month_day ?? 1,
                          run_on: s.run_on ?? "", expense: s.expense_review ?? initial.expense, sourceLibrary: s.source_library_id ?? 0,
                        } });
                      }}>{workspaceText("change")}</ActionButton>
                    )}
                    {data.my_groups.length > 0 && s.state !== "ended" && !s.expense_review && s.cadence !== "source" && (
                      <ActionButton type="button" className={secondary} disabled={busy} aria-expanded={sharing === s.id} onClick={() => { setSharing(sharing === s.id ? null : s.id); setPicked(s.shared_with_groups); }}>{workspaceText("share")}</ActionButton>
                    )}
                    <ActionButton type="button" className={secondary} aria-expanded={history === s.id} onClick={() => setHistory(history === s.id ? null : s.id)}>{workspaceText("history")}</ActionButton>
                    <ActionButton type="button" className={secondary} disabled={busy} onClick={() => {
                      const existingResults = s.expense_review ? "Completed reviews stay in Runs." : "Drafts it already made stay in My drafts.";
                      if (window.confirm(`Delete "${s.name}"? ${existingResults}`)) void run(async () => { await call(`${URL}/${s.id}`, "DELETE"); return `Deleted "${s.name}".`; });
                    }}>{workspaceText("delete")}</ActionButton>
                  </ResponsiveLayout>
                  {sharing === s.id && (
                    <fieldset className="mt-3 rounded-xl border border-border-01 p-3" data-testid="share-panel">
                      <legend className="px-1 text-sm font-medium text-text-05">{workspaceText("shareWithYourGroups")}</legend>
                      <p className="text-xs text-text-03">{workspaceText("peopleInTheseGroupsCanCopyItTheirCopy")}</p>
                      {data.my_groups.map((g) => (
                        <label key={g} className="flex min-h-11 items-center gap-2 text-sm text-text-05">
                          <NativeInput type="checkbox" checked={picked.includes(g)} onChange={(e) => setPicked(e.target.checked ? [...picked, g] : picked.filter((x) => x !== g))} />
                          {g}
                        </label>
                      ))}
                      <ActionButton type="button" className={secondary} disabled={busy} onClick={() => run(
                        // oxlint-disable-next-line react-doctor/no-impure-state-updater -- This callback is run by an event handler, outside React state updates.
                        async () => { await call(`${URL}/${s.id}/share`, "PUT", { version: s.version, groups: picked }); setSharing(null); return picked.length ? `Shared "${s.name}" with ${picked.join(", ")}.` : `"${s.name}" is no longer shared.`; })}>{workspaceText("saveSharing")}</ActionButton>
                    </fieldset>
                  )}
                  {history === s.id && <History id={s.id} focusRun={
                    manualRun?.scheduleId === s.id ? manualRun.runId : targetedSchedule === s.id ? targetedRun : null
                  } />}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {shared && shared.length > 0 && (
        <section aria-labelledby="sched-shared" className="flex flex-col gap-3" data-testid="shared-schedules">
          <h2 id="sched-shared" className="text-xl font-semibold text-text-05">{workspaceText("sharedWithYou")}</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {shared.map((x) => (
              <li key={x.id} id={`workflow-schedule-${x.id}`} tabIndex={x.id === targetedSchedule ? -1 : undefined}
                  className={`${card} flex flex-col gap-2 focus-visible:outline`} data-testid="shared-card">
                <h3 className="text-base font-semibold text-text-05">{x.name}</h3>
                <p className="text-xs text-text-03">{workspaceText("from")}{" "}{x.owner_email} · {x.when}</p>
                <p className="text-sm text-text-04"><span className="font-medium text-text-05">{x.title}.</span> {x.request.length > 220 ? `${x.request.slice(0, 220)}…` : x.request}</p>
                <div>
                  {x.already_copied ? (
                    <span className="text-sm text-text-03">{workspaceText("youHaveACopy")}</span>
                  ) : (
                    <ActionButton type="button" className={secondary} disabled={busy || !data?.scheduling_allowed} onClick={() => run(async () => { await call(`${URL}/${x.id}/copy`, "POST"); return `Copied "${x.name}". Your copy runs as you; change its time if you like.`; })}>{workspaceText("copyToMySchedules")}</ActionButton>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </ResponsiveLayout>
  );
}
