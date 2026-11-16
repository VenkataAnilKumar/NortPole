"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card, h1Class, pageClass } from "@/sections/sources/shared";
import IntegrationCatalog from "@/sections/sources/IntegrationCatalog";

interface Req {
  id: string; kind: string; item_key: string; item_name: string; reason: string; state: string;
  decided_by_email: string | null; decision_note: string; created_at: string; decided_at: string | null;
}
interface Item { kind: string; key: string; name: string; description: string; why_approval: string; my_request: Req | null }
interface Discover { items: Item[]; my_requests: Req[] }

const URL = "/api/sources/discover";
const GROUPS: { kind: string; heading: string; note: string }[] = [
  { kind: "connector", heading: "Connectors", note: "Company systems whose documents could be searched. You would only see what you can open there." },
  { kind: "skill", heading: "Skills", note: "Packs an administrator has uploaded but not turned on." },
  { kind: "plugin", heading: "Plugins", note: "Tools that exist here but chat assistants may not use yet." },
];
const STATE: Record<string, string> = { pending: "Requested", approved: "Approved", declined: "Declined", withdrawn: "Withdrawn" };
const KIND: Record<string, string> = { connector: "Connector", skill: "Skill", plugin: "Plugin" };
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";

async function post(url: string, body?: unknown): Promise<void> {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  }
}

function Status({ r }: { r: Req }) {
  return (
    <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04" data-testid="request-state">
      {STATE[r.state] ?? r.state}
    </span>
  );
}

/**
 * Discover: what this workspace supports but has not turned on, with a Request button for each. A request goes to the
 * administrators' Approvals page; approving it is a decision, and an administrator then sets the item up.
 */
export default function DiscoverPage() {
  const { data, error, isLoading, mutate } = useSWR<Discover>(URL, errorHandlingFetcher);
  const [asking, setAsking] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const run = async (fn: () => Promise<string>) => {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
      await mutate();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={pageClass} data-testid="discover-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>Discover</h1>
        <p className="text-sm text-text-03">
          The catalog of connectors and plugins: search it and install or connect right here. Below it, the other things you can ask an administrator to set up. Nothing is turned on by asking.
        </p>
      </header>
      <IntegrationCatalog />
      <h2 className="text-xl font-semibold text-text-05">Ask an administrator to set up</h2>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="discover-message">{msg.text}</p>}
      {isLoading && <p className="text-sm text-text-03">Loading…</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">Discover could not be loaded. Try again in a moment.</p>}
      {data && GROUPS.map((g) => {
        const items = data.items.filter((i) => i.kind === g.kind);
        return (
          <section key={g.kind} aria-labelledby={`disc-${g.kind}`} className="flex flex-col gap-2">
            <h2 id={`disc-${g.kind}`} className="text-xl font-semibold text-text-05">{g.heading}</h2>
            <p className="text-sm text-text-03">{g.note}</p>
            {items.length === 0 ? (
              <p className="text-sm text-text-03">Nothing more to add here.</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {items.map((i) => {
                  const id = `${i.kind}:${i.key}`;
                  const open = i.my_request?.state === "pending" || i.my_request?.state === "approved";
                  return (
                    <li key={id} className={`${card} flex flex-col gap-2`} data-testid="discover-item">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <h3 className="text-base font-semibold text-text-05">{i.name}</h3>
                        {i.my_request && <Status r={i.my_request} />}
                      </div>
                      {i.description && <p className="text-sm text-text-04">{i.description}</p>}
                      <p className="text-xs text-text-03">{i.why_approval}</p>
                      {i.my_request?.state === "approved" && (
                        <p className="text-xs text-text-04">Approved: an administrator will set it up.{i.my_request.decision_note ? ` Note: ${i.my_request.decision_note}` : ""}</p>
                      )}
                      {i.my_request?.state === "declined" && i.my_request.decision_note && (
                        <p className="text-xs text-text-04">Administrator&apos;s note: {i.my_request.decision_note}</p>
                      )}
                      {asking === id ? (
                        <div className="flex flex-col gap-2">
                          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
                            Why would it help? (optional)
                            <textarea
                              className="min-h-20 rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05"
                              maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)}
                            />
                          </label>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button" className={primary} disabled={busy}
                              onClick={() => run(async () => {
                                await post("/api/sources/requests", { kind: i.kind, item_key: i.key, reason });
                                setAsking(null);
                                setReason("");
                                return `Asked for ${i.name}. An administrator will decide; its status shows here.`;
                              })}
                            >
                              Send request
                            </button>
                            <button type="button" className={secondary} disabled={busy} onClick={() => { setAsking(null); setReason(""); }}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        !open && (
                          <div>
                            <button type="button" className={secondary} disabled={busy} onClick={() => { setAsking(id); setReason(""); setMsg(null); }} aria-label={`Request ${i.name}`}>
                              {i.my_request ? "Ask again" : "Request"}
                            </button>
                          </div>
                        )
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        );
      })}
      {data && data.my_requests.length > 0 && (
        <section className={card} aria-labelledby="disc-mine" data-testid="my-requests">
          <h2 id="disc-mine" className="text-base font-semibold text-text-05">Your requests</h2>
          <ul className="mt-2 flex flex-col divide-y divide-border-01">
            {data.my_requests.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span className="min-w-0 text-text-05">
                  {r.item_name} <span className="text-text-03">· {KIND[r.kind] ?? r.kind} · {new Date(r.created_at).toLocaleDateString()}</span>
                  {r.decision_note && <span className="block text-xs text-text-04">Note: {r.decision_note}</span>}
                </span>
                <span className="flex items-center gap-2">
                  <Status r={r} />
                  {r.state === "pending" && (
                    <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await post(`/api/sources/requests/${r.id}/withdraw`); return `Withdrew the request for ${r.item_name}.`; })}>
                      Withdraw
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
