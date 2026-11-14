"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Run {
  id: string; fired_at: string; outcome: string; reason: string | null; task_id: string | null; task_state: string | null;
  route_kind: string | null; input_tokens: number; output_tokens: number;
}
interface Schedule {
  id: string; name: string; title: string; pack_id: string | null; pack_template: string | null; cadence: string; at_time: string;
  timezone: string; weekday: number | null; month_day: number | null; run_on: string | null; when: string; next_run_at: string | null;
  state: string; pause_reason: string | null; pause_text: string | null; unaccepted_streak: number; last_run: Run | null;
  shared_with_groups: string[]; copied_from_id: string | null; version: number;
}
interface Mine { schedules: Schedule[]; scheduling_allowed: boolean; max_per_person: number; my_groups: string[] }
interface Shared { id: string; name: string; owner_email: string; when: string; title: string; request: string; desired_output: string; already_copied: boolean }
interface Template { id: string; title: string }
interface Pack { pack_id: string; name: string; templates: Template[]; ready_on_current_route: boolean }
interface Draft { id: string; title: string }

const URL = "/api/workflow-schedules";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const OUTCOME: Record<string, string> = {
  plan_ready: "Plan drafted", plan_failed: "Plan could not be drafted", skipped: "Skipped", paused: "Paused",
};
const TASK: Record<string, string> = {
  plan_review: "waiting for you", plan_accepted: "accepted", running: "running", draft_ready: "draft ready",
  run_failed: "run failed", approved: "approved", superseded: "replaced by a newer run", cancelled: "cancelled",
  plan_failed: "no plan", draft: "sent back to edit",
};

async function call(url: string, method: string, body?: unknown): Promise<any> {
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

interface FormValue {
  name: string; cadence: string; at_time: string; timezone: string; weekday: number; month_day: number; run_on: string;
  source: "template" | "draft" | "own"; pack: string; title: string; request: string;
}

function blank(): FormValue {
  let tz = "UTC";
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { /* keep UTC */ }
  return { name: "", cadence: "weekdays", at_time: "08:30", timezone: tz, weekday: 0, month_day: 1, run_on: "", source: "template", pack: "", title: "", request: "" };
}

/** The new-schedule and edit form. When editing only the name and timing change; what runs stays as it was saved. */
function ScheduleForm({ initial, editing, packs, draft, onDone, onCancel }: {
  initial: FormValue; editing: Schedule | null; packs: Pack[]; draft: Draft | null; onDone: (msg: string) => void; onCancel: () => void;
}) {
  const [v, setV] = useState<FormValue>(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (patch: Partial<FormValue>) => setV({ ...v, ...patch });
  const options = packs.filter((p) => p.ready_on_current_route).flatMap((p) => p.templates.map((t) => ({ key: `${p.pack_id}/${t.id}`, label: `${p.name}: ${t.title}` })));

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const timing = {
        cadence: v.cadence, at_time: v.at_time, timezone: v.timezone,
        weekday: v.cadence === "weekly" ? v.weekday : null, month_day: v.cadence === "monthly" ? v.month_day : null,
        run_on: v.cadence === "once" ? v.run_on || null : null,
      };
      if (editing) {
        await call(`${URL}/${editing.id}`, "PATCH", { version: editing.version, name: v.name, ...timing });
        onDone(`Saved "${v.name}".`);
      } else {
        const what = v.source === "draft" && draft ? { task_id: draft.id }
          : v.source === "template" ? { pack_id: v.pack.split("/")[0], pack_template: v.pack.split("/")[1] }
          : { title: v.title, request: v.request };
        await call(URL, "POST", { name: v.name, ...timing, ...what });
        onDone(`Scheduled "${v.name}". Each run prepares a plan and waits for you in Inbox.`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "The schedule could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const ready = v.name.trim() && v.at_time && v.timezone && (editing || (v.source === "draft" ? !!draft : v.source === "template" ? !!v.pack : v.title.trim() && v.request.trim()))
    && (v.cadence !== "once" || v.run_on);
  return (
    <section className={card} aria-labelledby="sched-form" data-testid="schedule-form">
      <h2 id="sched-form" className="text-base font-semibold text-text-05">{editing ? `Change "${editing.name}"` : "New schedule"}</h2>
      <p className="mt-1 text-sm text-text-03">Each run prepares a plan and waits for you in Inbox. Nothing runs further without your yes.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05 sm:col-span-2">
          Name
          <input className={input} value={v.name} maxLength={200} onChange={(e) => set({ name: e.target.value })} placeholder="for example: Monday policy check" />
        </label>
        {!editing && (
          <fieldset className="flex flex-col gap-2 sm:col-span-2">
            <legend className="mb-1 text-sm font-medium text-text-05">What runs</legend>
            {draft && (
              <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
                <input type="radio" name="source" checked={v.source === "draft"} onChange={() => set({ source: "draft" })} />
                Your draft: {draft.title || "Untitled draft"}
              </label>
            )}
            <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
              <input type="radio" name="source" checked={v.source === "template"} onChange={() => set({ source: "template" })} />
              A workflow
            </label>
            {v.source === "template" && (
              <label className="flex flex-col gap-1 text-sm text-text-04">
                <span className="sr-only">Workflow</span>
                <select className={input} value={v.pack} onChange={(e) => set({ pack: e.target.value })}>
                  <option value="">Choose a workflow</option>
                  {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                </select>
              </label>
            )}
            <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
              <input type="radio" name="source" checked={v.source === "own"} onChange={() => set({ source: "own" })} />
              Your own request
            </label>
            {v.source === "own" && (
              <div className="flex flex-col gap-2">
                <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
                  Title
                  <input className={input} value={v.title} maxLength={300} onChange={(e) => set({ title: e.target.value })} />
                </label>
                <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
                  Request
                  <textarea className={`${input} min-h-24 py-2`} value={v.request} maxLength={8000} onChange={(e) => set({ request: e.target.value })} />
                </label>
              </div>
            )}
          </fieldset>
        )}
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          How often
          <select className={input} value={v.cadence} onChange={(e) => set({ cadence: e.target.value })}>
            <option value="once">Once</option>
            <option value="daily">Every day</option>
            <option value="weekdays">Weekdays</option>
            <option value="weekly">Once a week</option>
            <option value="monthly">Once a month</option>
          </select>
        </label>
        {v.cadence === "weekly" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Day
            <select className={input} value={v.weekday} onChange={(e) => set({ weekday: Number(e.target.value) })}>
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </label>
        )}
        {v.cadence === "monthly" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Day of the month (1 to 28)
            <input className={input} type="number" min={1} max={28} value={v.month_day} onChange={(e) => set({ month_day: Number(e.target.value) })} />
          </label>
        )}
        {v.cadence === "once" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Date
            <input className={input} type="date" value={v.run_on} onChange={(e) => set({ run_on: e.target.value })} />
          </label>
        )}
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          Time
          <input className={input} type="time" value={v.at_time} onChange={(e) => set({ at_time: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          Time zone
          <input className={input} value={v.timezone} maxLength={64} onChange={(e) => set({ timezone: e.target.value })} />
        </label>
      </div>
      {err && <p role="alert" className="mt-2 text-sm text-status-text-error-05">{err}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={primary} disabled={busy || !ready} onClick={submit}>{busy ? "Saving…" : editing ? "Save" : "Schedule it"}</button>
        <button type="button" className={secondary} disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </section>
  );
}

function History({ id }: { id: string }) {
  const { data, error } = useSWR<Run[]>(`${URL}/${id}/runs`, errorHandlingFetcher);
  if (error) return <p className="mt-2 text-sm text-status-text-error-05">The history could not be loaded.</p>;
  if (!data) return <p className="mt-2 text-sm text-text-03">Loading…</p>;
  if (!data.length) return <p className="mt-2 text-sm text-text-03">No runs yet.</p>;
  return (
    <ol className="mt-2 flex flex-col divide-y divide-border-01" aria-label="Runs, newest first" data-testid="schedule-history">
      {data.map((r) => (
        <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2 text-sm">
          <span className="min-w-0 text-text-05">
            {when(r.fired_at)}: {OUTCOME[r.outcome] ?? r.outcome}
            {r.task_state && <> → {TASK[r.task_state] ?? r.task_state}</>}
            {r.reason && <span className="block text-xs text-text-03">{r.reason}</span>}
            {r.route_kind && <span className="block text-xs text-text-03">Planned on the {r.route_kind} route · {r.input_tokens + r.output_tokens} tokens</span>}
          </span>
          {r.task_id && <a href={`/app/workflows/drafts?task=${encodeURIComponent(r.task_id)}`} className="text-sm font-semibold text-text-05 underline">Open the draft</a>}
        </li>
      ))}
    </ol>
  );
}

/**
 * Scheduled workflows: each run drafts a plan as you and waits in Inbox. Create one from a workflow, a draft or your own
 * request; pause, resume, change, share with your groups or delete it; see what every run did. Shared schedules are
 * copied, so each copy is the copier's and runs as them.
 */
export default function ScheduledPage() {
  const params = useSearchParams();
  const { data, error, isLoading, mutate } = useSWR<Mine>(URL, errorHandlingFetcher);
  const { data: shared, mutate: mutateShared } = useSWR<Shared[]>(`${URL}/shared`, errorHandlingFetcher);
  const { data: packs } = useSWR<Pack[]>("/api/packs", errorHandlingFetcher);
  const taskId = params?.get("task");
  const { data: draft } = useSWR<Draft>(taskId ? `/api/tasks/${encodeURIComponent(taskId)}` : null, errorHandlingFetcher);
  const [form, setForm] = useState<{ initial: FormValue; editing: Schedule | null } | null>(null);
  const [history, setHistory] = useState<string | null>(null);
  const [sharing, setSharing] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Arriving from a workflow's or a draft's "Schedule" button opens the form for it.
  const preset = useMemo(() => {
    const pack = params?.get("pack"), template = params?.get("template");
    if (pack && template) return { ...blank(), source: "template" as const, pack: `${pack}/${template}` };
    if (taskId) return { ...blank(), source: "draft" as const };
    return null;
  }, [params, taskId]);
  useEffect(() => {
    if (preset && !form) setForm({ initial: preset, editing: null });
  }, [preset]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (fn: () => Promise<string>) => {
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
  };

  const schedules = data?.schedules ?? [];
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-8" data-testid="scheduled-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Scheduled</h1>
        <p className="text-sm text-text-03">
          Workflows that run on a schedule. Each run prepares a plan as you and waits in your Inbox; nothing runs further without your yes. A schedule pauses itself after 3 plans in a row are not accepted.
        </p>
      </header>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="scheduled-message">{msg.text}</p>}
      {isLoading && <p className="text-sm text-text-03">Loading…</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">Scheduled workflows could not be loaded. Try again in a moment.</p>}
      {data && !data.scheduling_allowed && (
        <section className={card} data-testid="scheduling-off">
          <h2 className="text-base font-semibold text-text-05">Scheduling is not turned on for you</h2>
          <p className="mt-1 text-sm text-text-03">An administrator decides who may schedule workflows. Your existing schedules are paused until it is on.</p>
        </section>
      )}
      {data && data.scheduling_allowed && !form && (
        <div>
          <button type="button" className={primary} onClick={() => { setMsg(null); setForm({ initial: blank(), editing: null }); }}>New schedule</button>
          <p className="mt-1 text-xs text-text-03">{schedules.filter((s) => s.state !== "ended").length} of {data.max_per_person} schedules in use.</p>
        </div>
      )}
      {form && (
        <ScheduleForm
          key={form.editing?.id ?? "new"}
          initial={form.initial}
          editing={form.editing}
          packs={packs ?? []}
          draft={draft ?? null}
          onDone={(text) => { setForm(null); setMsg({ ok: true, text }); void mutate(); }}
          onCancel={() => setForm(null)}
        />
      )}

      {data && (
        <section aria-labelledby="sched-mine" className="flex flex-col gap-3">
          <h2 id="sched-mine" className="text-xl font-semibold text-text-05">Your schedules</h2>
          {schedules.length === 0 ? (
            <p className="text-sm text-text-03">No schedules yet. Use “Schedule” on a workflow, or “Repeat on a schedule” on a finished draft.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {schedules.map((s) => (
                <li key={s.id} className={card} data-testid="schedule-card">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-text-05">{s.name}</h3>
                      <p className="text-sm text-text-03">{s.when}</p>
                    </div>
                    <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04" data-testid="schedule-state">
                      {s.state === "active" ? "Active" : s.state === "paused" ? "Paused" : "Finished"}
                    </span>
                  </div>
                  {s.pause_text && <p className="mt-2 rounded-xl bg-status-warning-01 px-3 py-2 text-sm text-text-05">{s.pause_text}</p>}
                  <dl className="mt-3 grid gap-1 text-sm text-text-03 sm:grid-cols-2">
                    <div><dt className="inline font-medium text-text-05">Next run: </dt><dd className="inline">{s.state === "active" ? when(s.next_run_at) : "none"}</dd></div>
                    <div><dt className="inline font-medium text-text-05">Last run: </dt><dd className="inline">{s.last_run ? `${OUTCOME[s.last_run.outcome] ?? s.last_run.outcome}, ${when(s.last_run.fired_at)}` : "none yet"}</dd></div>
                    <div className="sm:col-span-2"><dt className="inline font-medium text-text-05">Runs: </dt><dd className="inline">{s.title}{s.shared_with_groups.length ? ` · shared with ${s.shared_with_groups.join(", ")}` : ""}{s.copied_from_id ? " · a copy of a shared schedule" : ""}</dd></div>
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {s.state === "active" && (
                      <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await call(`${URL}/${s.id}/pause`, "POST", { version: s.version }); return `Paused "${s.name}".`; })}>Pause</button>
                    )}
                    {s.state === "paused" && data.scheduling_allowed && (
                      <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await call(`${URL}/${s.id}/resume`, "POST", { version: s.version }); return `Resumed "${s.name}".`; })}>Resume</button>
                    )}
                    {s.state !== "ended" && (
                      <button type="button" className={secondary} disabled={busy} onClick={() => { setMsg(null); setForm({ editing: s, initial: { ...blank(), name: s.name, cadence: s.cadence, at_time: s.at_time, timezone: s.timezone, weekday: s.weekday ?? 0, month_day: s.month_day ?? 1, run_on: s.run_on ?? "" } }); }}>Change</button>
                    )}
                    {data.my_groups.length > 0 && s.state !== "ended" && (
                      <button type="button" className={secondary} disabled={busy} aria-expanded={sharing === s.id} onClick={() => { setSharing(sharing === s.id ? null : s.id); setPicked(s.shared_with_groups); }}>Share</button>
                    )}
                    <button type="button" className={secondary} aria-expanded={history === s.id} onClick={() => setHistory(history === s.id ? null : s.id)}>History</button>
                    <button type="button" className={secondary} disabled={busy} onClick={() => { if (window.confirm(`Delete "${s.name}"? Drafts it already made stay in My drafts.`)) void run(async () => { await call(`${URL}/${s.id}`, "DELETE"); return `Deleted "${s.name}".`; }); }}>Delete</button>
                  </div>
                  {sharing === s.id && (
                    <fieldset className="mt-3 rounded-xl border border-border-01 p-3" data-testid="share-panel">
                      <legend className="px-1 text-sm font-medium text-text-05">Share with your groups</legend>
                      <p className="text-xs text-text-03">People in these groups can copy it. Their copy runs as them; you never see their drafts.</p>
                      {data.my_groups.map((g) => (
                        <label key={g} className="flex min-h-11 items-center gap-2 text-sm text-text-05">
                          <input type="checkbox" checked={picked.includes(g)} onChange={(e) => setPicked(e.target.checked ? [...picked, g] : picked.filter((x) => x !== g))} />
                          {g}
                        </label>
                      ))}
                      <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await call(`${URL}/${s.id}/share`, "PUT", { version: s.version, groups: picked }); setSharing(null); return picked.length ? `Shared "${s.name}" with ${picked.join(", ")}.` : `"${s.name}" is no longer shared.`; })}>Save sharing</button>
                    </fieldset>
                  )}
                  {history === s.id && <History id={s.id} />}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {shared && shared.length > 0 && (
        <section aria-labelledby="sched-shared" className="flex flex-col gap-3" data-testid="shared-schedules">
          <h2 id="sched-shared" className="text-xl font-semibold text-text-05">Shared with you</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {shared.map((x) => (
              <li key={x.id} className={`${card} flex flex-col gap-2`} data-testid="shared-card">
                <h3 className="text-base font-semibold text-text-05">{x.name}</h3>
                <p className="text-xs text-text-03">From {x.owner_email} · {x.when}</p>
                <p className="text-sm text-text-04"><span className="font-medium text-text-05">{x.title}.</span> {x.request.length > 220 ? `${x.request.slice(0, 220)}…` : x.request}</p>
                <div>
                  {x.already_copied ? (
                    <span className="text-sm text-text-03">You have a copy.</span>
                  ) : (
                    <button type="button" className={secondary} disabled={busy || !data?.scheduling_allowed} onClick={() => run(async () => { await call(`${URL}/${x.id}/copy`, "POST"); return `Copied "${x.name}". Your copy runs as you; change its time if you like.`; })}>Copy to my schedules</button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
