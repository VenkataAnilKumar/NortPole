"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Req {
  id: string; kind: string; item_name: string; reason: string; state: string; requested_by_email: string;
  decided_by_email: string | null; decision_note: string; created_at: string; manage_at: string;
}
interface Requests { pending: Req[]; recent: Req[] }

export const SOURCE_REQUESTS_URL = "/api/admin/source-requests";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const KIND: Record<string, string> = { connector: "Connector", skill: "Skill (pack)", plugin: "Plugin (tool)" };
const WHERE: Record<string, string> = { connector: "Connectors", skill: "Packs", plugin: "Tools" };

/**
 * What people asked for on Discover. Approving records the decision and tells the person; it does not turn anything
 * on, so each approved request links to the page where it is set up.
 */
export default function SourceRequestsQueue() {
  const { data, mutate } = useSWR<Requests>(SOURCE_REQUESTS_URL, errorHandlingFetcher, { refreshInterval: 30000 });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const decide = async (r: Req, approve: boolean) => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(`${SOURCE_REQUESTS_URL}/${r.id}/decide`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approve, note: notes[r.id] ?? "" }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : `The decision could not be saved (HTTP ${res.status}).`);
      }
      setMsg({ ok: true, text: approve ? `Approved. Set up ${r.item_name} on the ${WHERE[r.kind] ?? "relevant"} page; approving does not turn it on.` : `Declined. ${r.requested_by_email} sees your note.` });
      await mutate();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The decision could not be saved." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={card} aria-labelledby="src-req" data-testid="source-requests">
      <h2 id="src-req" className="text-base font-semibold text-text-05">Requests from people</h2>
      <p className="mt-1 text-sm text-text-03">
        Connectors, skills and plugins people asked for on Discover. Approving records your decision and shows it to them; you then set the item up where it is managed.
      </p>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`}>{msg.text}</p>}
      {!data || data.pending.length === 0 ? (
        <p className="mt-3 text-sm text-text-03">Nothing is waiting.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {data.pending.map((r) => (
            <li key={r.id} className="rounded-xl border border-border-01 px-3 py-3" data-testid="source-request">
              <p className="text-sm text-text-05">
                <span className="font-medium">{r.item_name}</span> <span className="text-text-03">· {KIND[r.kind] ?? r.kind} · from {r.requested_by_email} · {new Date(r.created_at).toLocaleString()}</span>
              </p>
              {r.reason && <p className="mt-1 whitespace-pre-wrap text-sm text-text-04">“{r.reason}”</p>}
              <label className="mt-2 flex flex-col gap-1 text-sm font-medium text-text-05">
                Note to {r.requested_by_email} (optional)
                <input
                  className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05"
                  maxLength={500} value={notes[r.id] ?? ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                />
              </label>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" className={primary} disabled={busy} onClick={() => decide(r, true)}>Approve</button>
                <button type="button" className={secondary} disabled={busy} onClick={() => decide(r, false)}>Decline</button>
                <a href={r.manage_at} className={`${secondary} inline-flex items-center`}>Open {WHERE[r.kind] ?? "its page"}</a>
              </div>
            </li>
          ))}
        </ul>
      )}
      {data && data.recent.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-text-05">Recently decided</h3>
          <ul className="mt-1 flex flex-col gap-1 text-sm text-text-04">
            {data.recent.map((r) => (
              <li key={r.id}>
                {r.state === "approved" ? "Approved" : "Declined"}: {r.item_name} for {r.requested_by_email} (by {r.decided_by_email})
                {r.state === "approved" && <> · <a href={r.manage_at} className="font-semibold text-text-05 underline">set it up</a></>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
