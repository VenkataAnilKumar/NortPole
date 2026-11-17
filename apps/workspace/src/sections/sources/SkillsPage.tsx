"use client";

import Link from "next/link";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card, h1Class, pageClass, titleCase } from "@/sections/sources/shared";
import MySkills from "@/sections/sources/MySkills";

interface Rule { severity: "block" | "warn"; message: string }
interface GuideRef { id: string; name: string; description: string }
interface Agent { id: string; name: string; description: string }
interface Template { id: string; title: string; style?: string; review_rules?: Rule[]; guides?: GuideRef[]; agent?: Agent | null }
interface Pack {
  pack_id: string; version: string; name: string; vertical: string; description: string;
  templates: Template[]; review_rules?: Rule[]; ready_on_current_route: boolean;
}

function unique<T extends { id: string }>(items: T[]): T[] {
  const seen = new Map<string, T>();
  items.forEach((i) => seen.set(i.id, i));
  return [...seen.values()];
}

/**
 * Skills: the know-how installed packs bring — guides, review rules, house style and workflow agents — so people can
 * see what shapes a draft before they start one. Read-only: packs are installed by administrators.
 */
export default function SkillsPage() {
  const { data, error, isLoading } = useSWR<Pack[]>("/api/packs", errorHandlingFetcher);
  const packs = [...(data ?? [])].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className={pageClass} data-testid="skills-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>Skills</h1>
        <p className="text-sm text-text-03">
          Your own skills, and what the installed packs know: the guides a draft follows, the rules it is checked against and the agents that prepare it. To use a pack,{" "}
          <Link href="/app/workflows" className="font-semibold text-text-05 underline">start a workflow</Link>. Administrators install and update packs.
        </p>
      </header>
      <MySkills />
      <h2 className="text-xl font-semibold text-text-05">Skills from packs</h2>
      {isLoading && <p className="text-sm text-text-03">Loading skills…</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">Skills could not be loaded. Try again in a moment.</p>}
      {data && packs.length === 0 && (
        <section className={card}>
          <h2 className="text-base font-semibold text-text-05">No skills yet</h2>
          <p className="mt-1 text-sm text-text-03">Skills appear here once an administrator installs and turns on a pack.</p>
        </section>
      )}
      <ul className="flex flex-col gap-3">
        {packs.map((p) => {
          const guides = unique(p.templates.flatMap((t) => t.guides ?? []));
          const agents = unique(p.templates.flatMap((t) => (t.agent ? [t.agent] : [])));
          const rules = [...(p.review_rules ?? []), ...p.templates.flatMap((t) => t.review_rules ?? [])];
          const styled = p.templates.filter((t) => t.style).length;
          return (
            <li key={p.pack_id} className={card} data-testid="skill-pack">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-text-05">{p.name}</h2>
                  <p className="text-xs text-text-03">{titleCase(p.vertical)} · version {p.version}</p>
                </div>
                {!p.ready_on_current_route && (
                  <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04">Not available on the current model</span>
                )}
              </div>
              {p.description && <p className="mt-2 text-sm text-text-04">{p.description}</p>}
              <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="font-medium text-text-05">Guides</dt>
                  <dd className="text-text-03">
                    {guides.length ? (
                      <ul className="mt-1 flex flex-col gap-1">{guides.map((g) => <li key={g.id}><span className="text-text-05">{g.name}</span>{g.description ? ` — ${g.description}` : ""}</li>)}</ul>
                    ) : "None"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-text-05">Workflow agents</dt>
                  <dd className="text-text-03">
                    {agents.length ? (
                      <ul className="mt-1 flex flex-col gap-1">{agents.map((a) => <li key={a.id}><span className="text-text-05">{a.name}</span>{a.description ? ` — ${a.description}` : ""}</li>)}</ul>
                    ) : "None"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-text-05">Review rules</dt>
                  <dd className="text-text-03">
                    {rules.length ? `${rules.filter((r) => r.severity === "block").length} must, ${rules.filter((r) => r.severity === "warn").length} should` : "None"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-text-05">Workflows</dt>
                  <dd className="text-text-03">
                    {p.templates.length} {p.templates.length === 1 ? "workflow" : "workflows"}{styled ? `, ${styled} with a house style` : ""}
                  </dd>
                </div>
              </dl>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
