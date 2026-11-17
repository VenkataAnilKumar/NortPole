"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Controls { second_for_route_policy: boolean; second_for_retention: boolean; second_for_packs: boolean; second_for_destinations: boolean; second_for_tools: boolean }
interface Change {
  id: string; kind: string; summary: string; state: string; proposed_by_email: string;
  decided_by_email: string | null; error: string | null; created_at: string; decided_at: string | null; own: boolean;
}
interface Changes { pending: Change[]; recent: Change[] }

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const KIND: Record<string, string> = { route_policy: "Route policy", retention: "Retention and legal hold", controls: "Approval rules", pack_signer: "Trusting a pack signer", pack_owner: "Pack key change", pack_activate: "Activating a pack version", send_target_create: "Registering a send destination", send_target_update: "Changing a send destination", tool_catalog: "Changing the tool catalog" };
const STATE: Record<string, string> = { applied: "Applied", declined: "Declined", cancelled: "Cancelled", expired: "Expired", failed: "Could not be applied" };

async function send(url: string, method: string, body?: unknown): Promise<any> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* not json */ }
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  return data;
}

/**
 * Administrator changes that need a second administrator, and the rules that say which. The rules are off by default:
 * with one administrator they would lock that person out of their own settings.
 */
export default function AdminApprovals() {
  const { data: controls, mutate: mutateControls } = useSWR<Controls>("/api/admin/controls", errorHandlingFetcher);
  const { data: changes, mutate: mutateChanges } = useSWR<Changes>("/api/admin/changes", errorHandlingFetcher, { refreshInterval: 30000 });
  const [draft, setDraft] = useState<Controls | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  if (!controls) return null;
  const rules = draft ?? controls;
  const dirty = draft !== null && (draft.second_for_route_policy !== controls.second_for_route_policy || draft.second_for_retention !== controls.second_for_retention || draft.second_for_packs !== controls.second_for_packs || draft.second_for_destinations !== controls.second_for_destinations || draft.second_for_tools !== controls.second_for_tools);

  const run = async (fn: () => Promise<string>) => {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." });
    } finally {
      await Promise.all([mutateControls(), mutateChanges()]);
      setBusy(false);
    }
  };

  return (
    <section className={card} aria-labelledby="apr-h" data-testid="admin-approvals">
      <h2 id="apr-h" className="text-base font-semibold text-text-05">Changes that need a second administrator</h2>
      <p className="mt-1 text-sm text-text-03">
        When a rule is on, a change of that kind does not take effect until a different administrator approves it. Both are recorded in the audit log.
        With only one administrator, leave these off: nobody could approve. Turning a rule on takes effect at once; changing the rules while one is on needs a second administrator too.
      </p>
      <fieldset className="mt-3 flex flex-col gap-1">
        <legend className="sr-only">Which changes need a second administrator</legend>
        <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input type="checkbox" className="h-4 w-4" checked={rules.second_for_route_policy} onChange={(e) => setDraft({ ...rules, second_for_route_policy: e.target.checked })} />
          Route policy: model routes, data classes and redaction
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input type="checkbox" className="h-4 w-4" checked={rules.second_for_retention} onChange={(e) => setDraft({ ...rules, second_for_retention: e.target.checked })} />
          Retention periods and the legal hold
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input type="checkbox" className="h-4 w-4" checked={rules.second_for_packs} onChange={(e) => setDraft({ ...rules, second_for_packs: e.target.checked })} />
          Packs: trusting a signer, a key change for a pack, and activating a version (revoking a signer is never held back)
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input type="checkbox" className="h-4 w-4" checked={rules.second_for_destinations} onChange={(e) => setDraft({ ...rules, second_for_destinations: e.target.checked })} />
          Send destinations: registering one or changing where drafts may be sent
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input type="checkbox" className="h-4 w-4" checked={rules.second_for_tools} onChange={(e) => setDraft({ ...rules, second_for_tools: e.target.checked })} />
          Tools: turning tool kinds or single tools on or off, and approving an outside tool
        </label>
      </fieldset>
      <div className="mt-2">
        <button
          type="button" className={secondary} disabled={busy || !dirty}
          onClick={() => run(async () => {
            const r = await send("/api/admin/controls", "PUT", draft);
            setDraft(null);
            return r?.pending_approval ? "Not applied yet: a second administrator has to approve this change to the rules." : "Saved.";
          })}
        >
          Save rules
        </button>
      </div>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="approvals-message">{msg.text}</p>}

      <h3 className="mt-5 text-sm font-semibold text-text-05">Waiting for approval</h3>
      {!changes || changes.pending.length === 0 ? (
        <p className="mt-1 text-sm text-text-03" data-testid="no-pending">Nothing is waiting.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-3">
          {changes.pending.map((c) => (
            <li key={c.id} className="rounded-xl border border-border-01 px-3 py-3" data-testid="pending-change">
              <p className="text-sm text-text-05"><span className="font-medium">{KIND[c.kind] ?? c.kind}</span>: {c.summary}</p>
              <p className="mt-1 text-xs text-text-03">Proposed by {c.own ? "you" : c.proposed_by_email} on {new Date(c.created_at).toLocaleString()}. It expires after 7 days.</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {c.own ? (
                  <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await send(`/api/admin/changes/${c.id}/cancel`, "POST"); return "Cancelled."; })}>Cancel my proposal</button>
                ) : (
                  <>
                    <button type="button" className={primary} disabled={busy} onClick={() => run(async () => { await send(`/api/admin/changes/${c.id}/approve`, "POST"); return "Approved and applied."; })}>Approve</button>
                    <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await send(`/api/admin/changes/${c.id}/decline`, "POST"); return "Declined."; })}>Decline</button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {changes && changes.recent.length > 0 && (
        <>
          <h3 className="mt-5 text-sm font-semibold text-text-05">Recently decided</h3>
          <ul className="mt-1 flex flex-col gap-1 text-sm text-text-04">
            {changes.recent.map((c) => (
              <li key={c.id}>{STATE[c.state] ?? c.state}: {c.summary}{c.decided_by_email ? ` (by ${c.decided_by_email})` : ""}{c.state === "failed" && c.error ? `: ${c.error}` : ""}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
