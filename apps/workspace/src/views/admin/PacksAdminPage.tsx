"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Signer {
  key_id: string;
  label: string;
  revoked: boolean;
}
interface Version {
  pack_id: string;
  version: string;
  name: string;
  vertical: string;
  active: boolean;
  signer_key_id: string;
  signer_revoked: boolean;
  digest: string;
  evaluation_cases: number;
  evaluations: { model_name: string; route_kind: string; passed: boolean; cases_passed: number; cases_total: number; failures: string[] }[];
  guides?: { id: string; name: string; description: string; body: string; used_by: string[] }[];
  agents?: { id: string; name: string; description: string; tool_labels: string[]; max_searches: number; guides: string[]; instructions: string; used_by: string[] }[];
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

/** The change was recorded but not applied: a second administrator has to approve it first. */
const HELD = "This change was not applied. It waits for a second administrator to approve it (Admin > Approvals).";

async function send(url: string, method: string, body?: unknown): Promise<string | null> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `The change could not be saved (HTTP ${res.status}).`);
  }
  return res.status === 202 ? HELD : null;
}

/**
 * Signed packs. A pack installs only when its signer is one you trust, the
 * signature matches the exact manifest, and the manifest is valid. Installing
 * does not activate it, and a pack's requested permissions grant nothing.
 */
export default function PacksAdminPage() {
  const { data: signers, mutate: refreshSigners } = useSWR<Signer[]>("/api/admin/pack-signers", errorHandlingFetcher);
  const { data: versions, mutate: refreshVersions } = useSWR<Version[]>("/api/admin/packs", errorHandlingFetcher);
  const [keyId, setKeyId] = useState("");
  const [pub, setPub] = useState("");
  const [pkg, setPkg] = useState("");
  const [handPack, setHandPack] = useState("");
  const [handTo, setHandTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // A pack belongs to the signer of its newest version; the list is newest first within each pack.
  const owners = new Map<string, string>();
  (versions ?? []).forEach((v) => { if (!owners.has(v.pack_id)) owners.set(v.pack_id, v.signer_key_id); });
  const handOwner = owners.get(handPack) ?? null;
  const handChoices = (signers ?? []).filter((x) => !x.revoked && x.key_id !== handOwner);

  const run = async (fn: () => Promise<string | null | void>) => {
    setBusy(true);
    setMessage(null);
    try {
      const held = await fn();
      if (held) setMessage(held);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "The change could not be saved.");
    } finally {
      await Promise.all([refreshSigners(), refreshVersions()]);
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-8" data-testid="packs-admin-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-text-05">Packs</h1>
        <p className="text-sm text-text-03">
          Install signed packs and choose the active version. Activating an older version is a rollback; drafts already
          started keep the version they began with.
        </p>
      </header>
      {message && <p role={message === HELD ? "status" : "alert"} data-testid="packs-message" className={`text-sm ${message === HELD ? "text-text-05" : "text-status-text-error-05"}`}>{message}</p>}

      <section className={card} aria-labelledby="signers-h">
        <h2 id="signers-h" className="mb-2 text-base font-semibold text-text-05">Trusted signers</h2>
        <ul className="mb-3 flex flex-col gap-2">
          {(signers ?? []).map((s) => (
            <li key={s.key_id} className="flex flex-wrap items-center justify-between gap-2 text-sm text-text-05" data-testid="signer-item">
              <span>{s.key_id}{s.label ? ` · ${s.label}` : ""}{s.revoked ? " · revoked" : ""}</span>
              {!s.revoked && (
                <button type="button" className={secondary} disabled={busy} onClick={() => run(() => send(`/api/admin/pack-signers/${encodeURIComponent(s.key_id)}/revoke`, "POST"))}>
                  Revoke
                </button>
              )}
            </li>
          ))}
          {(signers ?? []).length === 0 && <li className="text-sm text-text-03">No signer is trusted yet.</li>}
        </ul>
        <div className="flex flex-col gap-2">
          <input className={input} placeholder="Key id" value={keyId} onChange={(e) => setKeyId(e.target.value)} aria-label="Key id" />
          <input className={input} placeholder="Public key (base64, 32 bytes)" value={pub} onChange={(e) => setPub(e.target.value)} aria-label="Public key" />
          <div>
            <button
              type="button"
              className={primary}
              disabled={busy || !keyId.trim() || !pub.trim()}
              onClick={() => run(async () => { const held = await send("/api/admin/pack-signers", "POST", { key_id: keyId.trim(), public_key: pub.trim() }); setKeyId(""); setPub(""); return held; })}
            >
              Trust this signer
            </button>
          </div>
        </div>
      </section>

      <section className={card} aria-labelledby="hand-h" data-testid="key-change">
        <h2 id="hand-h" className="mb-1 text-base font-semibold text-text-05">Hand a pack to another signer</h2>
        <p className="mb-2 text-sm text-text-03">
          A pack belongs to the signer of its newest version; versions signed by anyone else are refused. To let another trusted signer publish the next version, allow it here (it works once, then that signer owns the pack). No approval is needed if the owner's key is revoked.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="flex flex-1 flex-col gap-1 text-sm font-medium text-text-05">Pack
            <select className={input} value={handPack} onChange={(e) => { setHandPack(e.target.value); setHandTo(""); }}>
              <option value="">Choose a pack</option>
              {[...owners.keys()].map((id) => <option key={id} value={id}>{id} (signed by {owners.get(id)})</option>)}
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm font-medium text-text-05">New signer
            <select className={input} value={handTo} onChange={(e) => setHandTo(e.target.value)} disabled={!handPack}>
              <option value="">Choose a trusted signer</option>
              {handChoices.map((x) => <option key={x.key_id} value={x.key_id}>{x.key_id}{x.label ? ` (${x.label})` : ""}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-2">
          <button type="button" className={secondary} disabled={busy || !handPack || !handTo} onClick={() => run(async () => { const held = await send(`/api/admin/packs/${encodeURIComponent(handPack)}/transfer`, "POST", { to_key_id: handTo }); setHandTo(""); return held; })}>
            Allow this signer to publish the next version
          </button>
        </div>
      </section>

      <section className={card} aria-labelledby="install-h">
        <h2 id="install-h" className="mb-2 text-base font-semibold text-text-05">Install a pack</h2>
        <textarea className={`${input} py-2 font-mono text-xs`} rows={6} placeholder='Paste the signed package ({"manifest": …, "signature": …, "key_id": …})' value={pkg} onChange={(e) => setPkg(e.target.value)} aria-label="Signed package" />
        <div className="mt-2">
          <button
            type="button"
            className={primary}
            disabled={busy || !pkg.trim()}
            onClick={() => run(async () => {
              let parsed: unknown;
              try {
                parsed = JSON.parse(pkg);
              } catch {
                throw new Error("That is not valid JSON.");
              }
              await send("/api/admin/packs", "POST", parsed);
              setPkg("");
            })}
          >
            Install (inactive until activated)
          </button>
        </div>
      </section>

      <section aria-labelledby="versions-h">
        <h2 id="versions-h" className="mb-2 text-base font-semibold text-text-05">Installed versions</h2>
        <ul className="flex flex-col gap-3">
          {(versions ?? []).map((v) => (
            <li key={`${v.pack_id}-${v.version}`} className={card} data-testid="version-item">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-base font-semibold text-text-05">{v.name} <span className="font-normal text-text-03">{v.version}</span></h3>
                  <p className="text-xs text-text-03">{v.pack_id} · {v.vertical} · signed by {v.signer_key_id} · digest {v.digest.slice(0, 12)}</p>
                  {v.signer_revoked && <p role="alert" className="mt-1 text-xs text-status-text-error-05">The signer was revoked: this pack is not offered and cannot be activated.</p>}
                </div>
                <div className="flex gap-2">
                  {v.evaluation_cases > 0 && (
                    <button type="button" className={secondary} disabled={busy} onClick={() => run(() => send(`/api/admin/packs/${v.pack_id}/${v.version}/evaluate`, "POST"))}>
                      Evaluate on current model
                    </button>
                  )}
                  {v.active ? (
                    <button type="button" className={secondary} disabled={busy} onClick={() => run(() => send(`/api/admin/packs/${v.pack_id}/deactivate`, "POST"))}>
                      Deactivate
                    </button>
                  ) : (
                    <button type="button" className={secondary} disabled={busy || v.signer_revoked} onClick={() => run(() => send(`/api/admin/packs/${v.pack_id}/${v.version}/activate`, "POST"))}>
                      Activate
                    </button>
                  )}
                </div>
              </div>
              {v.evaluation_cases > 0 && (
                <ul className="mt-2 text-xs text-text-03" data-testid="evaluations">
                  {v.evaluations.length === 0 && <li>Not evaluated yet. It will not run until it passes its {v.evaluation_cases} cases on the model in use.</li>}
                  {v.evaluations.map((e) => (
                    <li key={e.model_name} className={e.passed ? "" : "text-status-text-error-05"}>
                      {e.model_name} ({e.route_kind}): {e.passed ? "passed" : "failed"}, {e.cases_passed} of {e.cases_total} cases
                      {e.failures.map((f) => <div key={f}>{f}</div>)}
                    </li>
                  ))}
                </ul>
              )}
              {(v.agents ?? []).length > 0 && (
                <details className="mt-2 text-xs text-text-03" data-testid="admin-agents">
                  <summary className="cursor-pointer">Agents in this version ({(v.agents ?? []).length}): read their instructions before activating</summary>
                  <ul className="mt-1 flex flex-col gap-2">
                    {(v.agents ?? []).map((a) => (
                      <li key={a.id}>
                        <span className="font-medium text-text-05">{a.name}</span> · {a.description} · may {a.tool_labels.join("; ").toLowerCase()} (up to {a.max_searches} searches) · runs {a.used_by.length ? a.used_by.join(", ") : "no workflow"}{a.guides.length ? ` · follows ${a.guides.join(", ")}` : ""} · cannot send
                        <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1 text-text-05">{a.instructions}</pre>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {(v.guides ?? []).length > 0 && (
                <details className="mt-2 text-xs text-text-03" data-testid="admin-guides">
                  <summary className="cursor-pointer">Guides in this version ({(v.guides ?? []).length}): read them before activating</summary>
                  <ul className="mt-1 flex flex-col gap-2">
                    {(v.guides ?? []).map((g) => (
                      <li key={g.id}>
                        <span className="font-medium text-text-05">{g.name}</span> · {g.description} · used by {g.used_by.length ? g.used_by.join(", ") : "no workflow"}
                        <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1 text-text-05">{g.body}</pre>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {v.active && <p className="mt-2 text-xs text-text-03" data-testid="active-flag">Active: people see this version.</p>}
            </li>
          ))}
          {(versions ?? []).length === 0 && <li className="text-sm text-text-03">No pack is installed.</li>}
        </ul>
      </section>
    </div>
  );
}
