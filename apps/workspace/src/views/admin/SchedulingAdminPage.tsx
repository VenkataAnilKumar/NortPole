"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Controls { version: number; enabled: boolean; source_events_enabled: boolean; groups: string[]; max_per_person: number }
interface Row { id: string; owner_email: string; when: string; state: string; pause_reason: string | null; next_run_at: string | null; last_outcome: string | null; last_fired_at: string | null }
interface Group { id: number; name: string }

const BASE = "/api/admin/workflow-schedules";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const th = "py-2 pr-3 text-left font-medium text-text-03";
const td = "py-2 pr-3 align-top text-text-05";
const REASON: Record<string, string> = {
  unaccepted: "3 plans not accepted", skipped: "3 runs without a plan", scheduling_off: "scheduling off for the owner",
  owner_inactive: "owner not active", admin: "paused by an administrator", owner: "paused by the owner",
};

async function call(url: string, method: string, body?: Omit<Controls, "version">): Promise<any> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  return data;
}

/**
 * Who may schedule workflows, and every schedule in the workspace. Scheduling is off until turned on here. Each run
 * only drafts a plan for its owner; administrators see owners and timing, never what a schedule asks for.
 */
export default function SchedulingAdminPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data: c, mutate: mutateControls } = useSWR<Controls>(`${BASE}/controls`, errorHandlingFetcher);
  const { data: rows, mutate: mutateRows } = useSWR<Row[]>(BASE, errorHandlingFetcher);
  const { data: groups } = useSWR<Group[]>("/api/admin/access-groups", errorHandlingFetcher, { shouldRetryOnError: false });
  const [draft, setDraft] = useState<Controls | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => { if (c && !draft) setDraft(c); }, [c]);

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
      await Promise.all([mutateControls(), mutateRows()]);
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-5xl flex-col gap-5 p-4 sm:p-8" data-testid="scheduling-admin-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("scheduling")}</h1>
        <p className="mt-1 text-sm text-text-03">{workspaceText("scheduledWorkflowsRunAsTheirOwnerAndStopAt")}</p>
      </div>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="scheduling-message">{msg.text}</p>}

      {draft && (
        <section className={card} aria-labelledby="sch-who">
          <h2 id="sch-who" className="text-base font-semibold text-text-05">{workspaceText("whoMaySchedule")}</h2>
          <label className="mt-3 flex min-h-11 items-center gap-2 text-sm text-text-05">
            <NativeInput type="checkbox" checked={draft.enabled} onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })} data-testid="scheduling-enabled" />{workspaceText("schedulingIsOn")}</label>
          <p className="text-xs text-text-03">{workspaceText("turningItOffPausesEveryScheduleAtItsNext")}</p>
          <label className="mt-3 flex min-h-11 items-center gap-2 text-sm text-text-05">
            <NativeInput type="checkbox" checked={draft.source_events_enabled} disabled={!draft.enabled} onChange={(e) => setDraft({ ...draft, source_events_enabled: e.target.checked })} />{workspaceText("allowKnowledgeChangeTriggers")}</label>
          {draft.enabled && (
            <fieldset className="mt-3">
              <legend className="text-sm font-medium text-text-05">{workspaceText("groupsNoneTickedMeansEveryone")}</legend>
              {(groups ?? []).length === 0 ? (
                <p className="text-sm text-text-03">{workspaceText("noGroupsEveryoneMaySchedule")}</p>
              ) : (
                (groups ?? []).map((g) => (
                  <label key={g.id} className="flex min-h-11 items-center gap-2 text-sm text-text-05">
                    <NativeInput type="checkbox" checked={draft.groups.includes(g.name)}
                      onChange={(e) => setDraft({ ...draft, groups: e.target.checked ? [...draft.groups, g.name] : draft.groups.filter((x) => x !== g.name) })} />
                    {g.name}
                  </label>
                ))
              )}
            </fieldset>
          )}
          <label className="mt-3 flex max-w-xs flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("mostSchedulesPerPerson1To50")}<NativeInput className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05" type="number" min={1} max={50}
              value={draft.max_per_person} onChange={(e) => setDraft({ ...draft, max_per_person: Number(e.target.value) })} />
          </label>
          <ActionButton type="button" className={`${primary} mt-3`} disabled={busy}
            onClick={() => run(
              // oxlint-disable-next-line react-doctor/no-impure-state-updater -- This callback is run by an event handler, outside React state updates.
              async () => {
              const saved = await call(`${BASE}/controls`, "PUT", { enabled: draft.enabled, source_events_enabled: draft.source_events_enabled, groups: draft.groups, max_per_person: draft.max_per_person });
              setDraft(saved);
              return saved.enabled ? `Scheduling is on${saved.groups.length ? ` for ${saved.groups.join(", ")}` : " for everyone"}.` : "Scheduling is off.";
            })}>{workspaceText("save")}</ActionButton>
        </section>
      )}

      <section className={card} aria-labelledby="sch-all">
        <ResponsiveLayout display="flex" className="flex-wrap items-baseline justify-between gap-2">
          <h2 id="sch-all" className="text-base font-semibold text-text-05">{workspaceText("everySchedule")}</h2>
          <ActionButton type="button" className={secondary} disabled={busy}
            onClick={() => run(async () => { const r = await call(`${BASE}/run-due`, "POST"); return `Ran what was due: ${r.fired} schedule${r.fired === 1 ? "" : "s"}.`; })}>{workspaceText("runWhatIsDueNow")}</ActionButton>
        </ResponsiveLayout>
        <p className="mt-1 text-xs text-text-03">{workspaceText("theBackgroundWorkerDoesThisEveryFiveMinutesUse")}</p>
        {!rows ? (
          <p className="mt-3 text-sm text-text-03">{workspaceText("loading")}</p>
        ) : rows.length === 0 ? (
          <p className="mt-3 text-sm text-text-03">{workspaceText("noSchedulesYet")}</p>
        ) : (
          <div className="mt-3 overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={workspaceText("everySchedule")} tabIndex={0}>
            <table className="w-full text-sm">
              <thead>
                <tr><th scope="col" className={th}>{workspaceText("owner")}</th><th scope="col" className={th}>{workspaceText("when")}</th><th scope="col" className={th}>{workspaceText("state")}</th><th scope="col" className={th}>{workspaceText("nextRun_6c03cb")}</th><th scope="col" className={th}>{workspaceText("lastRun_333c63")}</th><th scope="col" className={th}><span className="sr-only">{workspaceText("actions")}</span></th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-border-01" data-testid="scheduling-row">
                    <th scope="row" className={`${td} text-left font-medium`}>{r.owner_email}</th>
                    <td className={td}>{r.when}</td>
                    <td className={td}>{r.state}{r.pause_reason ? ` (${REASON[r.pause_reason] ?? r.pause_reason})` : ""}</td>
                    <td className={td}>{r.next_run_at ? new Date(r.next_run_at).toLocaleString() : "none"}</td>
                    <td className={td}>{r.last_outcome ? `${r.last_outcome.replace("_", " ")}, ${r.last_fired_at ? new Date(r.last_fired_at).toLocaleString() : ""}` : "none"}</td>
                    <td className={td}>
                      {r.state === "active" && (
                        <ActionButton type="button" className={secondary} disabled={busy} aria-label={`Pause the schedule of ${r.owner_email}`}
                          onClick={() => run(async () => { await call(`${BASE}/${r.id}/pause`, "POST"); return `Paused. ${r.owner_email} is told in their Inbox.`; })}>{workspaceText("pause")}</ActionButton>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </ResponsiveLayout>
  );
}
