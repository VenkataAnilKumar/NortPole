"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Kind { kind: string; label: string; on: boolean; default: boolean }
interface ToolRow {
  id: number; name: string; kind: string; source: string; host: string | null; core_enabled: boolean;
  allowed: boolean; override: boolean | null; personal: boolean; agents: number; agent_names: string[];
  approval: string | null; server_id: number | null; description: string; definition_preview: string;
}
interface Catalog { version: number; kinds: Kind[]; tools: ToolRow[]; code_mode_switched_on: boolean }

const URL = "/api/admin/tool-catalog";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const th = "py-2 pr-3 text-left font-medium text-text-03";
const td = "py-2 pr-3 text-text-05 align-top";
const RISK: Record<string, string> = {
  read: "Stays inside the workspace.",
  web: "Reaches outside sites; a page can carry instructions, and an address can carry text out.",
  generate: "Sends the prompt to the image model.",
  personal: "Writes only to the person's own memory.",
  code: "Code the model writes is run, and its results come back into the chat.",
  outside: "Calls systems outside the product. Each tool also needs its own approval below, which records its definition; a changed definition stops it until approved again.",
};

async function put(body: unknown): Promise<Catalog> {
  const res = await fetch(URL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `The change could not be saved (HTTP ${res.status}).`);
  return data as Catalog;
}

/**
 * Which tools chat agents may use. Every tool the product can give a chat agent is listed with its kind; a kind or a
 * single tool can be turned off, and a tool that is off is never offered to the model. Code and outside tools start off.
 */
export default function ToolCatalogPage() {
  const { data, error, isLoading, mutate } = useSWR<Catalog>(URL, errorHandlingFetcher);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const save = async (kinds: Record<string, boolean>, tools: Record<string, boolean>, approve: string[] = []) => {
    setBusy(true);
    setMsg(null);
    try {
      await mutate(await put({ kinds, tools, approve }), { revalidate: false });
      setMsg({ ok: true, text: "Saved. It applies to the next message in every chat." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The change could not be saved." });
    } finally {
      setBusy(false);
    }
  };
  const kindMap = (d: Catalog) => Object.fromEntries(d.kinds.map((k) => [k.kind, k.on]));
  const overrides = (d: Catalog) => Object.fromEntries(d.tools.filter((t) => t.override !== null).map((t) => [String(t.id), t.override as boolean]));

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 p-4 sm:p-8" data-testid="tool-catalog-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">Tools</h1>
        <p className="mt-1 text-sm text-text-03">
          What chat agents may use. A tool that is off here is never offered to the model, whatever an agent is set up with. Running code and calling outside
          systems start off. Drafts are not affected: they use no tools.
        </p>
      </div>
      {error && <p role="alert" className="text-sm text-status-text-error-05">The tool list could not be loaded.</p>}
      {isLoading && <p className="text-sm text-text-03">Loading…</p>}
      {data && (
        <>
          <section className={card} aria-labelledby="tc-kinds">
            <h2 id="tc-kinds" className="text-base font-semibold text-text-05">Kinds of tool</h2>
            <ul className="mt-3 flex flex-col gap-2">
              {data.kinds.map((k) => (
                <li key={k.kind} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-01 px-3 py-2" data-testid="tc-kind">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-text-05">{k.label}</p>
                    <p className="text-xs text-text-03">{RISK[k.kind]} Default: {k.default ? "on" : "off"}.</p>
                  </div>
                  <label className="flex min-h-11 items-center gap-2 text-sm text-text-05">
                    <input
                      type="checkbox" className="h-4 w-4" checked={k.on} disabled={busy}
                      onChange={(e) => save({ ...kindMap(data), [k.kind]: e.target.checked }, overrides(data))}
                    />
                    {k.on ? "On" : "Off"}
                  </label>
                </li>
              ))}
            </ul>
            {data.code_mode_switched_on && (
              <p className="mt-2 text-xs text-text-03">Code mode is switched on in the server settings; it also needs “Run code in a sandbox” on here.</p>
            )}
            {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="tc-message">{msg.text}</p>}
          </section>

          <section className={card} aria-labelledby="tc-tools">
            <h2 id="tc-tools" className="text-base font-semibold text-text-05">Every tool</h2>
            <p className="mt-1 text-sm text-text-03">A setting on one tool overrides its kind. “Agents” counts chat agents that have the tool attached.</p>
            <div className="mt-3 overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label="Every tool" tabIndex={0}>
              <table className="w-full text-sm">
                <thead>
                  <tr><th scope="col" className={th}>Tool</th><th scope="col" className={th}>Kind</th><th scope="col" className={th}>From</th><th scope="col" className={th}>Agents</th><th scope="col" className={th}>Allowed</th><th scope="col" className={th}>Setting</th></tr>
                </thead>
                <tbody>
                  {data.tools.map((t) => (
                    <tr key={t.id} className="border-t border-border-01" data-testid="tc-tool">
                      <th scope="row" className={`${td} text-left font-medium`}>
                        {t.name}
                        {t.personal && <span className="block text-xs font-normal text-text-03">Added by one person for themselves</span>}
                        {!t.core_enabled && <span className="block text-xs font-normal text-text-03">Switched off in its own settings too</span>}
                        {t.approval && (
                          <span className={`block text-xs font-normal ${t.approval === "approved" ? "text-text-03" : "text-status-text-error-05"}`} data-testid="tc-approval">
                            Definition: {t.approval}
                          </span>
                        )}
                        {t.approval && (
                          <details className="mt-1 text-xs font-normal text-text-03">
                            <summary className="cursor-pointer">What the model is told, and the arguments it sends</summary>
                            <p className="mt-1 whitespace-pre-wrap text-text-05">{t.description || "(no description)"}</p>
                            {t.definition_preview && <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-background-neutral-01 px-2 py-1 text-text-05">{t.definition_preview}</pre>}
                          </details>
                        )}
                        {t.approval && t.approval !== "approved" && (
                          <button
                            type="button" className={`${secondary} mt-1`} disabled={busy}
                            onClick={() => save(kindMap(data), { ...overrides(data), [String(t.id)]: true }, [String(t.id)])}
                          >
                            {t.approval === "not approved" ? "Approve this definition" : "Approve the new definition"}
                          </button>
                        )}
                        {t.server_id !== null && (
                          <button
                            type="button" className={`${secondary} mt-1 ml-2`} disabled={busy}
                            onClick={async () => {
                              setBusy(true);
                              setMsg(null);
                              try {
                                const res = await fetch(`${URL}/check/${t.server_id}`, { method: "POST" });
                                const body = await res.json().catch(() => null);
                                if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `The check failed (HTTP ${res.status}).`);
                                const changed = (body as { name: string; status: string }[]).filter((r) => r.status !== "unchanged");
                                setMsg({ ok: changed.length === 0, text: changed.length ? `Differences: ${changed.map((r) => `${r.name} (${r.status})`).join("; ")}` : "The server's tools match what was approved." });
                                await mutate();
                              } catch (e) {
                                setMsg({ ok: false, text: e instanceof Error ? e.message : "The check failed." });
                              } finally {
                                setBusy(false);
                              }
                            }}
                          >
                            Check the server now
                          </button>
                        )}
                      </th>
                      <td className={td}>{t.kind}</td>
                      <td className={td}>{t.source}{t.host ? ` (${t.host})` : ""}</td>
                      <td className={td} title={t.agent_names.join(", ")}>{t.agents}</td>
                      <td className={`${td} ${t.allowed ? "" : "text-status-text-error-05"}`}>{t.allowed ? "Yes" : "No"}</td>
                      <td className={td}>
                        <label className="sr-only" htmlFor={`tc-${t.id}`}>Setting for {t.name}</label>
                        <select
                          id={`tc-${t.id}`} className="min-h-11 rounded-lg border border-border-01 bg-background-neutral-00 px-2 text-text-05" disabled={busy}
                          value={t.override === null ? "kind" : t.override ? "on" : "off"}
                          onChange={(e) => {
                            const next = { ...overrides(data) };
                            if (e.target.value === "kind") delete next[String(t.id)];
                            else next[String(t.id)] = e.target.value === "on";
                            save(kindMap(data), next);
                          }}
                        >
                          <option value="kind">Follow its kind</option>
                          <option value="on">Always on</option>
                          <option value="off">Always off</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <p className="text-xs text-text-03"><button type="button" className={secondary} disabled={busy} onClick={() => save(Object.fromEntries(data.kinds.map((k) => [k.kind, k.default])), {})}>Put every setting back to the defaults</button></p>
        </>
      )}
    </div>
  );
}
