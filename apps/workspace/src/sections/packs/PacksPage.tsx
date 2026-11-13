"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Template {
  id: string;
  title: string;
  request: string;
  desired_output: string;
  style?: string;
  review_rules?: Rule[];
  guides?: { id: string; name: string; description: string }[];
  agent?: { id: string; name: string; description: string; tool_labels: string[]; max_searches: number; guides: string[]; may_send: boolean } | null;
}
interface Rule {
  kind: string;
  value?: number | string | null;
  severity: "block" | "warn";
  message: string;
}
interface Pack {
  pack_id: string;
  version: string;
  name: string;
  vertical: string;
  description: string;
  templates: Template[];
  data_classes: string[];
  route_kinds: string[];
  requests_send_destinations: boolean;
  ready_on_current_route: boolean;
  readiness_note: string | null;
  group?: "everyday" | "domain";
  autonomy?: string;
  review_rules?: Rule[];
  signer_key_id?: string;
  evaluation_cases?: number;
  passed_models?: string[];
}

const AUTONOMY: Record<string, string> = {
  act_with_approval: "Can prepare a send; you approve the exact content before anything leaves.",
  draft_only: "Prepares drafts only: its results can be reviewed but never sent from the product.",
};

function title(s: string): string {
  return s.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Everyday packs first, then one group per domain, each sorted by name. */
function groups(packs: Pack[]): { key: string; heading: string; note: string; items: Pack[] }[] {
  const everyday = packs.filter((p) => p.group === "everyday");
  const domains = new Map<string, Pack[]>();
  packs.filter((p) => p.group !== "everyday").forEach((p) => domains.set(p.vertical, [...(domains.get(p.vertical) ?? []), p]));
  const byName = (a: Pack, b: Pack) => a.name.localeCompare(b.name);
  const out = [];
  if (everyday.length) out.push({ key: "everyday", heading: "Everyday", note: "Workflows any team can use.", items: everyday.sort(byName) });
  [...domains.keys()].sort().forEach((d) => out.push({ key: d, heading: title(d), note: `Workflows for ${title(d).toLowerCase()} work.`, items: (domains.get(d) ?? []).sort(byName) }));
  return out;
}

function Rules({ rules }: { rules: Rule[] }) {
  if (!rules.length) return null;
  return (
    <ul className="mt-1 flex flex-col gap-0.5">
      {rules.map((r, i) => (
        <li key={i} className="text-xs text-text-04">
          <span className="font-semibold">{r.severity === "block" ? "Must" : "Should"}:</span> {r.message}
        </li>
      ))}
    </ul>
  );
}

function Details({ p }: { p: Pack }) {
  const templateRules = p.templates.filter((t) => (t.review_rules ?? []).length || t.style);
  return (
    <dl className="mt-3 grid gap-3 rounded-xl bg-background-neutral-01 p-3 text-xs text-text-04 sm:grid-cols-2" data-testid="pack-details">
      <div>
        <dt className="font-semibold text-text-05">Where it may run</dt>
        <dd>{p.route_kinds.join(", ")} model routes, for {p.data_classes.join(", ")} data.</dd>
      </div>
      <div>
        <dt className="font-semibold text-text-05">Checked on</dt>
        <dd>
          {(p.evaluation_cases ?? 0) === 0
            ? "This pack has no evaluation cases."
            : (p.passed_models ?? []).length
              ? `Passed its ${p.evaluation_cases} evaluation case${p.evaluation_cases === 1 ? "" : "s"} on ${(p.passed_models ?? []).join(", ")}.`
              : `Not yet passed its ${p.evaluation_cases} evaluation case${p.evaluation_cases === 1 ? "" : "s"} on any model.`}
        </dd>
      </div>
      <div>
        <dt className="font-semibold text-text-05">What it may do</dt>
        <dd>
          {AUTONOMY[p.autonomy ?? "act_with_approval"] ?? p.autonomy}
          {p.requests_send_destinations ? " It asks to send results to a destination; an administrator decides." : ""}
        </dd>
      </div>
      <div>
        <dt className="font-semibold text-text-05">Version and signer</dt>
        <dd>
          Version {p.version}, signed by {p.signer_key_id || "a trusted signer"}. A draft keeps the version it started from.
        </dd>
      </div>
      {p.templates.some((t) => t.agent) && (
        <div className="sm:col-span-2" data-testid="agent-card">
          <dt className="font-semibold text-text-05">Run by an agent</dt>
          <dd>
            {p.templates.filter((t) => t.agent).map((t) => (
              <div key={t.id} className="mt-1">
                <span className="text-text-05">{t.title}:</span> <span className="text-text-05">{t.agent!.name}</span>. {t.agent!.description}{" "}
                It may: {t.agent!.tool_labels.join("; ").toLowerCase().replace("the person can open", "you can open")} (up to {t.agent!.max_searches} searches, as you).
                {t.agent!.guides.length > 0 ? ` It follows: ${t.agent!.guides.join(", ")}.` : ""} You accept its plan before it runs. It cannot send anything.
              </div>
            ))}
          </dd>
        </div>
      )}
      {p.templates.some((t) => (t.guides ?? []).length > 0) && (
        <div className="sm:col-span-2" data-testid="pack-guides">
          <dt className="font-semibold text-text-05">Guides it follows</dt>
          <dd>
            Written know-how from the pack. A guide shapes how the work is done; it is not a source and cannot change the citation rules.
            {p.templates.filter((t) => (t.guides ?? []).length > 0).map((t) => (
              <div key={t.id} className="mt-1">
                <span className="text-text-05">{t.title}:</span>{" "}
                {(t.guides ?? []).map((g, i) => (
                  <span key={g.id}>{i > 0 ? "; " : ""}<span className="text-text-05">{g.name}</span> ({g.description})</span>
                ))}
              </div>
            ))}
          </dd>
        </div>
      )}
      {((p.review_rules ?? []).length > 0 || templateRules.length > 0) && (
        <div className="sm:col-span-2">
          <dt className="font-semibold text-text-05">What it checks before you approve</dt>
          <dd>
            <Rules rules={p.review_rules ?? []} />
            {templateRules.map((t) => (
              <div key={t.id} className="mt-1">
                <span className="text-text-05">{t.title}:</span>
                {t.style ? <span> house style "{t.style}"</span> : null}
                <Rules rules={t.review_rules ?? []} />
              </div>
            ))}
          </dd>
        </div>
      )}
    </dl>
  );
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

/**
 * Workflows page: packs of ready-made tasks (Everyday, then each domain). Picking one
 * makes a draft task you can edit; nothing runs until you press Start, and the
 * pack only runs on the model routes and data classes it lists.
 */
export default function PacksPage() {
  const router = useRouter();
  const { data, error, isLoading } = useSWR<Pack[]>("/api/packs", errorHandlingFetcher);
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const packs = data ?? [];

  const use = async (pack: Pack, t: Template) => {
    setBusy(`${pack.pack_id}/${t.id}`);
    setFailed(null);
    try {
      const res = await fetch(`/api/packs/${pack.pack_id}/templates/${t.id}/task`, { method: "POST" });
      if (!res.ok) {
        let detail = "";
        try {
          detail = (await res.json())?.detail ?? "";
        } catch {
          /* no body */
        }
        throw new Error(typeof detail === "string" && detail ? detail : `Could not create the draft (HTTP ${res.status}).`);
      }
      const created = (await res.json()) as { id: string };
      router.push(`/app/workflows/drafts?task=${encodeURIComponent(created.id)}`);
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "Could not create the draft.");
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-8" data-testid="packs-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Start a workflow</h1>
        <p className="text-sm text-text-03">
          Ready-made workflows, grouped in packs. Choosing one creates a draft for you to edit; nothing runs until
          you press Start.
        </p>
      </header>
      {failed && <p role="alert" className="text-sm text-status-text-error-05">{failed}</p>}

      {isLoading ? (
        <p className="text-sm text-text-03">Loading…</p>
      ) : error ? (
        <p role="alert" className="text-sm text-text-05">Workflows could not be loaded.</p>
      ) : packs.length === 0 ? (
        <section className={card}>
          <h2 className="mb-1 text-base font-semibold text-text-05">No packs are active</h2>
          <p className="text-sm text-text-03">An administrator installs and activates signed packs. Until then, write your own under Drafts.</p>
        </section>
      ) : (
        <div className="flex flex-col gap-8">
          {groups(packs).map((g) => (
            <section key={g.key} aria-labelledby={`group-${g.key}`} data-testid="pack-group">
              <h2 id={`group-${g.key}`} className="text-xl font-semibold text-text-05">{g.heading}</h2>
              <p className="mb-3 text-sm text-text-03">{g.note}</p>
              <ul className="flex flex-col gap-4">
                {g.items.map((p) => (
            <li key={p.pack_id} className={card} data-testid="pack-card">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-lg font-semibold text-text-05">{p.name}</h3>
                      <p className="text-xs text-text-03">{p.group === "everyday" ? "Everyday" : title(p.vertical)} · version {p.version}</p>
                    </div>
                    <button
                      type="button"
                      className="min-h-10 rounded-xl px-3 text-sm font-semibold text-text-05 underline-offset-2 hover:underline"
                      aria-expanded={open === p.pack_id}
                      aria-controls={`details-${p.pack_id}`}
                      onClick={() => setOpen(open === p.pack_id ? null : p.pack_id)}
                    >
                      {open === p.pack_id ? "Hide details" : "Details"}
                    </button>
                  </div>
                  {p.description && <p className="mt-2 text-sm text-text-03">{p.description}</p>}
                  {open === p.pack_id && <div id={`details-${p.pack_id}`}><Details p={p} /></div>}
                  {!p.ready_on_current_route && <p role="status" className="mt-2 text-xs text-status-text-warning-05" data-testid="not-ready">{p.readiness_note}</p>}
                  <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                    {p.templates.map((t) => (
                      <li key={t.id} className="flex flex-col justify-between gap-2 rounded-xl border border-border-01 p-3">
                        <div>
                          <div className="text-sm font-semibold text-text-05">{t.title}</div>
                          <div className="mt-1 text-xs text-text-03">{t.request}</div>
                        </div>
                        <button type="button" className={secondary} disabled={!!busy || !p.ready_on_current_route} onClick={() => use(p, t)}>
                          {busy === `${p.pack_id}/${t.id}` ? "Creating…" : "Start a draft"}
                        </button>
                      </li>
                    ))}
                  </ul>
                </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
