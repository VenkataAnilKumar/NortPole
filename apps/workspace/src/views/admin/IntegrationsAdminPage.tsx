"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { categoryLabel, GROUP_LABEL, KIND_LABEL } from "@/sections/sources/integrations";

type Answer = "allowed" | "needs_approval" | "blocked";
interface Row {
  id: string; name: string; kind: string; group: "horizontal" | "vertical"; category: string; has_writes: boolean;
  default: Answer; override: Answer | null; category_override: Answer | null; effective: Answer; installs: number; connected: number;
}
interface Policy { config: { integrations: Record<string, Answer>; categories: Record<string, Answer> }; items: Row[] }

const URL = "/api/admin/integrations/policy";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const select = "min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-2 text-sm text-text-05";
const ANSWER: Record<Answer, string> = { allowed: "Allowed", needs_approval: "Needs approval", blocked: "Blocked" };

/**
 * Who may use each integration. "Allowed" lets people install and connect it themselves; "Needs approval" makes a person
 * ask first; "Blocked" stops everyone. An answer on one integration beats one on its category, which beats the
 * integration's own default, and blocked anywhere wins. Letting everyone use a write action needs a confirmation.
 */
export default function IntegrationsAdminPage() {
  const { data, error, isLoading, mutate } = useSWR<Policy>(URL, errorHandlingFetcher);
  const [items, setItems] = useState<Record<string, Answer>>({});
  const [cats, setCats] = useState<Record<string, Answer>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [needsConfirm, setNeedsConfirm] = useState(false);

  useEffect(() => {
    if (data) { setItems(data.config.integrations); setCats(data.config.categories); }
  }, [data]);

  const save = async (acknowledge: boolean) => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(URL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ config: { integrations: items, categories: cats }, acknowledge_writes: acknowledge }) });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        const detail = typeof body?.detail === "string" ? body.detail : `The change could not be saved (HTTP ${res.status}).`;
        setNeedsConfirm(detail.includes("without asking first"));
        throw new Error(detail);
      }
      await mutate(body as Policy, { revalidate: false });
      setNeedsConfirm(false);
      setMsg({ ok: true, text: "Saved. It applies to the next install, connect or call." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The change could not be saved." });
    } finally {
      setBusy(false);
    }
  };

  const set = (target: "item" | "cat", key: string, value: string) => {
    const apply = (m: Record<string, Answer>) => { const next = { ...m }; if (value === "") delete next[key]; else next[key] = value as Answer; return next; };
    if (target === "item") setItems(apply); else setCats(apply);
    setNeedsConfirm(false);
  };
  const dirty = data !== undefined && (JSON.stringify(items) !== JSON.stringify(data.config.integrations) || JSON.stringify(cats) !== JSON.stringify(data.config.categories));
  const rows = data?.items ?? [];

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-8" data-testid="integrations-admin-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Integrations</h1>
        <p className="text-sm text-text-03">Who may use each connector and plugin. Changes are recorded in the audit log.</p>
      </header>
      {isLoading && <p className="text-sm text-text-03">Loading…</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">The policy could not be loaded. Try again in a moment.</p>}
      <p role={msg?.ok === false ? "alert" : "status"} className={`min-h-5 text-sm ${msg?.ok === false ? "text-status-text-error-05" : "text-text-05"}`} data-testid="integrations-message">{msg?.text ?? ""}</p>
      {needsConfirm && (
        <div className={`${card} flex flex-wrap items-center justify-between gap-3`} role="group" aria-label="Confirm">
          <p className="text-sm text-text-05">This lets people use actions that change things in outside systems without asking first.</p>
          <button type="button" className={primary} disabled={busy} onClick={() => save(true)}>Confirm and save</button>
        </div>
      )}
      {(["horizontal", "vertical"] as const).map((g) => {
        const inGroup = rows.filter((r) => r.group === g);
        if (inGroup.length === 0) return null;
        const categories = [...new Set(inGroup.map((r) => r.category))];
        return (
          <section key={g} aria-labelledby={`pol-${g}`} className="flex flex-col gap-3">
            <h2 id={`pol-${g}`} className="font-[family-name:var(--font-serif)] text-2xl font-medium text-text-05">{GROUP_LABEL[g]}</h2>
            {categories.map((c) => {
              const key = `${g}/${c}`;
              return (
                <div key={c} className={card} data-testid="policy-category">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-base font-semibold text-text-05">{categoryLabel(c)}</h3>
                    <label className="flex items-center gap-2 text-sm text-text-04">
                      Whole category
                      <select className={select} value={cats[key] ?? ""} onChange={(e) => set("cat", key, e.target.value)} aria-label={`Policy for the whole ${categoryLabel(c)} category`}>
                        <option value="">Use each one&apos;s own</option>
                        {(Object.keys(ANSWER) as Answer[]).map((a) => <option key={a} value={a}>{ANSWER[a]}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full min-w-[34rem] text-sm">
                      <caption className="sr-only">{categoryLabel(c)} integrations and who may use them</caption>
                      <thead>
                        <tr><th scope="col" className="py-2 pr-3 text-left font-medium text-text-03">Integration</th><th scope="col" className="py-2 pr-3 text-left font-medium text-text-03">Policy</th><th scope="col" className="py-2 pr-3 text-left font-medium text-text-03">In force</th><th scope="col" className="py-2 text-right font-medium text-text-03">Installed / connected</th></tr>
                      </thead>
                      <tbody>
                        {inGroup.filter((r) => r.category === c).map((r) => (
                          <tr key={r.id} className="border-t border-border-01" data-testid="policy-row">
                            <th scope="row" className="py-2 pr-3 text-left align-top font-normal text-text-05">
                              <span className="font-medium">{r.name}</span>
                              <span className="block text-xs text-text-03">{KIND_LABEL[r.kind]}{r.has_writes ? " · can change things" : " · reads only"} · its default: {ANSWER[r.default]}</span>
                            </th>
                            <td className="py-2 pr-3 align-top">
                              <select className={select} value={items[r.id] ?? ""} onChange={(e) => set("item", r.id, e.target.value)} aria-label={`Policy for ${r.name}`}>
                                <option value="">Use the default</option>
                                {(Object.keys(ANSWER) as Answer[]).map((a) => <option key={a} value={a}>{ANSWER[a]}</option>)}
                              </select>
                            </td>
                            <td className="py-2 pr-3 align-top text-text-05" data-testid="policy-effective">{ANSWER[r.effective]}</td>
                            <td className="py-2 text-right align-top tabular-nums text-text-04">{r.installs} / {r.connected}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
          </section>
        );
      })}
      {data && (
        <div className="flex flex-wrap gap-2">
          <button type="button" className={primary} disabled={busy || !dirty} onClick={() => save(false)}>Save changes</button>
          <button type="button" className={secondary} disabled={busy || !dirty} onClick={() => { setItems(data.config.integrations); setCats(data.config.categories); setNeedsConfirm(false); setMsg(null); }}>Discard changes</button>
        </div>
      )}
    </div>
  );
}
