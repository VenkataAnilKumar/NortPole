"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Retention {
  audit_days: number | null;
  usage_days: number | null;
  legal_hold: boolean;
  hold_reason: string;
  hold_set_by: string | null;
  last_prune_at: string | null;
  last_prune_summary: string | null;
  min_days: number;
  max_days: number;
  placeholder_note: string;
}

const URL = "/api/admin/retention";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

async function call(url: string, method: string, body?: unknown): Promise<any> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* not json */
  }
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Request failed (HTTP ${res.status}).`);
  return data;
}

/** How long records are kept, a legal hold that stops all deletion, and a download of the audit log. */
export default function RetentionPanel() {
  const { data } = useSWR<Retention>(URL, errorHandlingFetcher);
  const [auditDays, setAuditDays] = useState<string>("");
  const [usageDays, setUsageDays] = useState<string>("");
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!data) return null;

  const run = async (fn: () => Promise<string>) => {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
      await mutate(URL);
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Failed." });
    } finally {
      setBusy(false);
    }
  };
  const save = (hold: boolean) =>
    run(async () => {
      for (const v of [auditDays, usageDays]) {
        if (v && (!/^\d+$/.test(v) || Number(v) < data.min_days || Number(v) > data.max_days)) {
          throw new Error(`Periods must be whole numbers of days from ${data.min_days} to ${data.max_days}.`);
        }
      }
      await call(URL, "PUT", {
        audit_days: auditDays ? Number(auditDays) : data.audit_days,
        usage_days: usageDays ? Number(usageDays) : data.usage_days,
        legal_hold: hold,
        hold_reason: hold ? reason || data.hold_reason : "",
        keep_audit_forever: data.audit_days === null && !auditDays,
        keep_usage_forever: data.usage_days === null && !usageDays,
      });
      return hold ? "Legal hold is on: nothing is deleted." : "Saved.";
    });

  return (
    <section className={card} aria-labelledby="retention-h" data-testid="retention-panel">
      <h2 id="retention-h" className="text-base font-semibold text-text-05">Retention, legal hold and export</h2>
      <p className="mt-1 text-sm text-text-03">{data.placeholder_note}</p>
      {data.legal_hold && (
        <p role="status" className="mt-3 rounded-xl bg-status-warning-01 px-3 py-2 text-sm text-text-05" data-testid="hold-banner">
          Legal hold is on ({data.hold_reason}; set by {data.hold_set_by ?? "an administrator"}). Nothing is being deleted.
        </p>
      )}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          Keep audit events for (days, {data.min_days} to {data.max_days})
          <input className={input} inputMode="numeric" value={auditDays} onChange={(e) => setAuditDays(e.target.value)} placeholder={data.audit_days === null ? "forever" : String(data.audit_days)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          Keep usage and redaction counts for (days)
          <input className={input} inputMode="numeric" value={usageDays} onChange={(e) => setUsageDays(e.target.value)} placeholder={data.usage_days === null ? "forever" : String(data.usage_days)} />
        </label>
      </div>
      <label className="mt-3 flex flex-col gap-1 text-sm font-medium text-text-05">
        Reason for a legal hold
        <input className={input} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={data.hold_reason || "for example: case or audit reference"} />
      </label>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={secondary} disabled={busy} onClick={() => save(data.legal_hold)}>Save periods</button>
        {data.legal_hold ? (
          <button type="button" className={secondary} disabled={busy} onClick={() => save(false)}>Lift legal hold</button>
        ) : (
          <button type="button" className={secondary} disabled={busy || !reason.trim()} onClick={() => save(true)}>Place legal hold</button>
        )}
        <button
          type="button"
          className={secondary}
          disabled={busy}
          onClick={() => run(async () => {
            const r = await call(`${URL}/prune`, "POST");
            return r.held ? "Nothing was deleted: a legal hold is on." : `Deleted ${r.audit_events} audit events, ${r.usage_rows} usage rows, ${r.redaction_rows} redaction rows.`;
          })}
        >
          Run the prune now
        </button>
        <button
          type="button"
          className={secondary}
          disabled={busy}
          onClick={() => run(async () => {
            const r = await call("/api/admin/audit/verify", "GET");
            if (r.ok) return `The audit chain is intact: ${r.checked} events checked${r.unhashed_rows ? `; ${r.unhashed_rows} older events predate the chain and are not covered` : ""}. Latest hash ${String(r.head_hash).slice(0, 12)}…`;
            throw new Error(`The audit chain is broken at event ${r.first_break.id}: ${r.first_break.reason}.`);
          })}
        >
          Check audit integrity
        </button>
        <a className={`${secondary} inline-flex items-center`} href="/api/admin/audit/export?format=csv" download>Download audit log (CSV)</a>
        <a className={`${secondary} inline-flex items-center`} href="/api/admin/audit/export?format=json" download>Download audit log (JSON)</a>
      </div>
      <p className="mt-2 text-xs text-text-03">
        The prune also runs daily when the background workers are running. Exports hold up to 50,000 events (with their hashes) and are themselves recorded in the audit log. The integrity check finds an edited event or one removed from the middle; it cannot see the newest events being removed unless the latest hash was kept elsewhere (each event's log line carries it).
        {data.last_prune_summary ? ` Last prune: ${data.last_prune_summary}.` : ""}
      </p>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="retention-message">{msg.text}</p>}
    </section>
  );
}
