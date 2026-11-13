"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Guide { id: string; name: string; description: string; body: string }
interface Agent { id: string; name: string; description: string; instructions: string; tools: string[]; max_searches: number; guides: string[] }
interface Template { id: string; title: string; request: string; desired_output: string; guides: string[]; agent: string | null }
interface Manifest {
  schema_version: 1; id: string; name: string; version: string; vertical: string; description: string;
  templates: Template[]; requires: { data_classes: string[]; route_kinds: string[] };
  autonomy: "draft_only" | "act_with_approval"; guides: Guide[]; agents: Agent[];
}
interface Problem { where: string; message: string }

const CLASSES = ["public", "internal", "confidential", "restricted"];
const ROUTES = ["local", "private", "cloud"];
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const area = "min-h-24 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const label = "flex flex-col gap-1 text-sm font-medium text-text-05";

const starter = (): Manifest => ({
  schema_version: 1, id: "my-workflows", name: "My workflows", version: "1.0.0", vertical: "general", description: "",
  templates: [{ id: "cited-answer", title: "Cited answer", request: "Answer the question from the policies, with a citation for each point.", desired_output: "", guides: ["cite-each-point"], agent: "researcher" }],
  requires: { data_classes: ["internal", "confidential"], route_kinds: ["local"] },
  autonomy: "draft_only",
  guides: [{ id: "cite-each-point", name: "Cite each point", description: "Use for any answer drawn from policies.", body: "State each point in one sentence and cite the passage it comes from. If no passage covers it, say so." }],
  agents: [{ id: "researcher", name: "Researcher", description: "Finds the relevant passages and cites them.", instructions: "Search for the exact rule first, then for exceptions.", tools: ["search"], max_searches: 2, guides: ["cite-each-point"] }],
});

async function call(url: string, method: string, body?: unknown): Promise<any> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  return data;
}

function Checks({ legend, options, value, onChange }: { legend: string; options: string[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <fieldset className="flex flex-wrap gap-3">
      <legend className="mb-1 text-sm font-medium text-text-05">{legend}</legend>
      {options.length === 0 && <span className="text-xs text-text-03">None yet.</span>}
      {options.map((o) => (
        <label key={o} className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input type="checkbox" className="h-4 w-4" checked={value.includes(o)} onChange={(e) => onChange(e.target.checked ? [...value, o] : value.filter((x) => x !== o))} />
          {o}
        </label>
      ))}
    </fieldset>
  );
}

/**
 * Studio: write a pack here instead of signing one outside. It is checked with the same rules as any pack, signed with
 * this workspace's own key, and installed as an inactive version that you review and activate on the Packs page.
 */
export default function StudioPage() {
  const { data: drafts, mutate } = useSWR<Record<string, Manifest>>("/api/admin/studio", errorHandlingFetcher);
  const [m, setM] = useState<Manifest | null>(null);
  const [problems, setProblems] = useState<Problem[] | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<string>) => {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." });
    } finally {
      setBusy(false);
    }
  };
  const set = (patch: Partial<Manifest>) => m && setM({ ...m, ...patch });
  const upd = <T,>(list: T[], i: number, patch: Partial<T>) => list.map((x, j) => (j === i ? { ...x, ...patch } : x));
  const guideIds = m?.guides.map((g) => g.id) ?? [];

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 p-4 sm:p-8" data-testid="studio-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">Studio</h1>
        <p className="mt-1 text-sm text-text-03">
          Write workflows, guides and an agent for this workspace. Publishing checks the pack with the same rules as any pack, signs it with this
          workspace&apos;s own key, and installs it inactive: read it and activate it on the Packs page. A Studio pack shows that an administrator here
          published it; it does not show that it came from an outside author.
        </p>
      </div>

      <section className={card} aria-labelledby="st-drafts">
        <h2 id="st-drafts" className="text-base font-semibold text-text-05">Drafts</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(drafts ?? {}).map(([id, d]) => (
            <button key={id} type="button" className={secondary} onClick={() => { setM(d); setProblems(null); setMsg(null); }}>{d.name || id} {d.version}</button>
          ))}
          <button type="button" className={secondary} onClick={() => { setM(starter()); setProblems(null); setMsg(null); }}>Start a new pack</button>
        </div>
      </section>

      {m && (
        <>
          <section className={card} aria-labelledby="st-pack">
            <h2 id="st-pack" className="text-base font-semibold text-text-05">The pack</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className={label}>Id (lower-case letters, digits and hyphens)<input className={input} value={m.id} onChange={(e) => set({ id: e.target.value })} /></label>
              <label className={label}>Name<input className={input} value={m.name} onChange={(e) => set({ name: e.target.value })} /></label>
              <label className={label}>Version (like 1.0.0; a change needs a new one)<input className={input} value={m.version} onChange={(e) => set({ version: e.target.value })} /></label>
              <label className={label}>Domain (&ldquo;general&rdquo; for everyday workflows)<input className={input} value={m.vertical} onChange={(e) => set({ vertical: e.target.value })} /></label>
            </div>
            <label className={`${label} mt-3`}>Description<textarea className={area} value={m.description} onChange={(e) => set({ description: e.target.value })} /></label>
            <div className="mt-3 flex flex-col gap-2">
              <Checks legend="Data classes it may work with" options={CLASSES} value={m.requires.data_classes} onChange={(v) => set({ requires: { ...m.requires, data_classes: v } })} />
              <Checks legend="Model routes it may run on" options={ROUTES} value={m.requires.route_kinds} onChange={(v) => set({ requires: { ...m.requires, route_kinds: v } })} />
              <label className={label}>
                How far its drafts may go
                <select className={input} value={m.autonomy} onChange={(e) => set({ autonomy: e.target.value as Manifest["autonomy"] })}>
                  <option value="draft_only">Draft only: a send can be prepared but never approved or sent</option>
                  <option value="act_with_approval">Act with approval: a person approves the exact content before it is sent</option>
                </select>
              </label>
            </div>
          </section>

          <section className={card} aria-labelledby="st-guides">
            <h2 id="st-guides" className="text-base font-semibold text-text-05">Guides</h2>
            <p className="text-sm text-text-03">Written know-how. Text only; a guide cannot add a source, run anything or change a rule.</p>
            {m.guides.map((g, i) => (
              <fieldset key={i} className="mt-3 flex flex-col gap-2 rounded-xl border border-border-01 p-3" data-testid="st-guide">
                <legend className="px-1 text-sm font-medium text-text-05">Guide {i + 1}</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className={label}>Id<input className={input} value={g.id} onChange={(e) => set({ guides: upd(m.guides, i, { id: e.target.value }) })} /></label>
                  <label className={label}>Name<input className={input} value={g.name} onChange={(e) => set({ guides: upd(m.guides, i, { name: e.target.value }) })} /></label>
                </div>
                <label className={label}>When to use it<input className={input} value={g.description} onChange={(e) => set({ guides: upd(m.guides, i, { description: e.target.value })})} /></label>
                <label className={label}>Text (up to 4,000 characters)<textarea className={area} value={g.body} onChange={(e) => set({ guides: upd(m.guides, i, { body: e.target.value }) })} /></label>
                <div><button type="button" className={secondary} onClick={() => set({ guides: m.guides.filter((_, j) => j !== i) })}>Remove this guide</button></div>
              </fieldset>
            ))}
            <button type="button" className={`${secondary} mt-3`} onClick={() => set({ guides: [...m.guides, { id: "", name: "", description: "", body: "" }] })}>Add a guide</button>
          </section>

          <section className={card} aria-labelledby="st-agents">
            <h2 id="st-agents" className="text-base font-semibold text-text-05">Agents</h2>
            <p className="text-sm text-text-03">An agent proposes searches; the person accepts them before anything runs, and the product runs them as that person. It cannot send anything.</p>
            {m.agents.map((a, i) => (
              <fieldset key={i} className="mt-3 flex flex-col gap-2 rounded-xl border border-border-01 p-3" data-testid="st-agent">
                <legend className="px-1 text-sm font-medium text-text-05">Agent {i + 1}</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className={label}>Id<input className={input} value={a.id} onChange={(e) => set({ agents: upd(m.agents, i, { id: e.target.value }) })} /></label>
                  <label className={label}>Name<input className={input} value={a.name} onChange={(e) => set({ agents: upd(m.agents, i, { name: e.target.value }) })} /></label>
                </div>
                <label className={label}>What it does (shown to people)<input className={input} value={a.description} onChange={(e) => set({ agents: upd(m.agents, i, { description: e.target.value }) })} /></label>
                <label className={label}>Instructions (up to 2,000 characters; administrators see them)<textarea className={area} value={a.instructions} onChange={(e) => set({ agents: upd(m.agents, i, { instructions: e.target.value }) })} /></label>
                <Checks legend="Tools it may use" options={["search"]} value={a.tools} onChange={(v) => set({ agents: upd(m.agents, i, { tools: v }) })} />
                <label className={label}>
                  Most searches per run
                  <select className={input} value={a.max_searches} onChange={(e) => set({ agents: upd(m.agents, i, { max_searches: Number(e.target.value) }) })}>
                    {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
                <Checks legend="Guides it follows" options={guideIds} value={a.guides} onChange={(v) => set({ agents: upd(m.agents, i, { guides: v }) })} />
                <div><button type="button" className={secondary} onClick={() => set({ agents: m.agents.filter((_, j) => j !== i) })}>Remove this agent</button></div>
              </fieldset>
            ))}
            <button type="button" className={`${secondary} mt-3`} onClick={() => set({ agents: [...m.agents, { id: "", name: "", description: "", instructions: "", tools: ["search"], max_searches: 2, guides: [] }] })}>Add an agent</button>
          </section>

          <section className={card} aria-labelledby="st-workflows">
            <h2 id="st-workflows" className="text-base font-semibold text-text-05">Workflows</h2>
            {m.templates.map((t, i) => (
              <fieldset key={i} className="mt-3 flex flex-col gap-2 rounded-xl border border-border-01 p-3" data-testid="st-template">
                <legend className="px-1 text-sm font-medium text-text-05">Workflow {i + 1}</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className={label}>Id<input className={input} value={t.id} onChange={(e) => set({ templates: upd(m.templates, i, { id: e.target.value }) })} /></label>
                  <label className={label}>Title<input className={input} value={t.title} onChange={(e) => set({ templates: upd(m.templates, i, { title: e.target.value }) })} /></label>
                </div>
                <label className={label}>Request<textarea className={area} value={t.request} onChange={(e) => set({ templates: upd(m.templates, i, { request: e.target.value }) })} /></label>
                <label className={label}>Desired output<input className={input} value={t.desired_output} onChange={(e) => set({ templates: upd(m.templates, i, { desired_output: e.target.value }) })} /></label>
                <Checks legend="Guides it uses (up to three)" options={guideIds} value={t.guides} onChange={(v) => set({ templates: upd(m.templates, i, { guides: v }) })} />
                <label className={label}>
                  Run by
                  <select className={input} value={t.agent ?? ""} onChange={(e) => set({ templates: upd(m.templates, i, { agent: e.target.value || null }) })}>
                    <option value="">No agent (a plain workflow)</option>
                    {m.agents.map((a) => <option key={a.id} value={a.id}>{a.name || a.id}</option>)}
                  </select>
                </label>
                <div><button type="button" className={secondary} onClick={() => set({ templates: m.templates.filter((_, j) => j !== i) })}>Remove this workflow</button></div>
              </fieldset>
            ))}
            <button type="button" className={`${secondary} mt-3`} onClick={() => set({ templates: [...m.templates, { id: "", title: "", request: "", desired_output: "", guides: [], agent: null }] })}>Add a workflow</button>
          </section>

          <section className={card} aria-labelledby="st-actions">
            <h2 id="st-actions" className="text-base font-semibold text-text-05">Check, save and publish</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => {
                const r = await call("/api/admin/studio/check", "POST", { manifest: m });
                setProblems(r.problems);
                return r.ok ? "No problems found." : `${r.problems.length} problem(s) found.`;
              })}>Check</button>
              <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => {
                const r = await call(`/api/admin/studio/${encodeURIComponent(m.id)}`, "PUT", { manifest: m });
                setProblems(r.problems);
                await mutate();
                return r.ok ? "Saved. No problems found." : `Saved with ${r.problems.length} problem(s); fix them before publishing.`;
              })}>Save draft</button>
              <button type="button" className={primary} disabled={busy} onClick={() => run(async () => {
                await call(`/api/admin/studio/${encodeURIComponent(m.id)}`, "PUT", { manifest: m });
                const v = await call(`/api/admin/studio/${encodeURIComponent(m.id)}/publish`, "POST");
                await mutate();
                return `Published ${v.pack_id} ${v.version} as an inactive version. Read it and activate it on the Packs page.`;
              })}>Publish (installs inactive)</button>
              <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => {
                await call(`/api/admin/studio/${encodeURIComponent(m.id)}`, "DELETE");
                await mutate();
                setM(null);
                return "Draft deleted. Published versions are not affected.";
              })}>Delete draft</button>
            </div>
            {msg && <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="st-message">{msg.text}</p>}
            {problems && problems.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-status-text-error-05" data-testid="st-problems">
                {problems.map((p, i) => <li key={i}><span className="font-medium">{p.where}</span>: {p.message}</li>)}
              </ul>
            )}
            <details className="mt-3 text-xs text-text-03">
              <summary className="cursor-pointer">The pack as it will be signed (JSON)</summary>
              <pre className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1 text-text-05">{JSON.stringify(m, null, 2)}</pre>
            </details>
          </section>
        </>
      )}
    </div>
  );
}
