"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { NavLink } from "@opal/navigation";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card, h1Class, pageClass, titleCase } from "@/sections/sources/shared";
import BuiltInSkills from "@/sections/sources/BuiltInSkills";
import SkillsManager from "@/views/SkillsPage";

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
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, error, isLoading } = useSWR<Pack[]>("/api/packs", errorHandlingFetcher);
  const packs = [...(data ?? [])].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className={pageClass} data-testid="skills-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>{workspaceText("skills")}</h1>
        <p className="text-sm text-text-03">{workspaceText("yourOwnSkillsAndWhatTheInstalledPacksKnow")}{" "}
          <NavLink href="/app/workflows" className="font-semibold text-text-05 underline">{workspaceText("startAWorkflow")}</NavLink>{workspaceText("administratorsInstallAndUpdatePacks")}</p>
      </header>
      <BuiltInSkills />
      <SkillsManager surface="sources" />
      <h2 className="text-xl font-semibold text-text-05">{workspaceText("skillsFromPacks")}</h2>
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loadingSkills")}</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("skillsCouldNotBeLoadedTryAgainInA")}</p>}
      {data && packs.length === 0 && (
        <section className={card}>
          <p className="mt-1 text-sm text-text-03">{workspaceText("skillsAppearHereOnceAnAdministratorInstallsAndTurns")}</p>
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
              <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-text-05">{p.name}</h2>
                  <p className="text-xs text-text-03">{titleCase(p.vertical)}{" "}{workspaceText("version")}{" "}{p.version}</p>
                </div>
                {!p.ready_on_current_route && (
                  <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04">{workspaceText("notAvailableOnTheCurrentModel")}</span>
                )}
              </ResponsiveLayout>
              {p.description && <p className="mt-2 text-sm text-text-04">{p.description}</p>}
              <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="font-medium text-text-05">{workspaceText("guides")}</dt>
                  <dd className="text-text-03">
                    {guides.length ? (
                      <ul className="mt-1 flex flex-col gap-1">{guides.map((g) => <li key={g.id}><span className="text-text-05">{g.name}</span>{g.description ? ` · ${g.description}` : ""}</li>)}</ul>
                    ) : "None"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-text-05">{workspaceText("workflowAgents")}</dt>
                  <dd className="text-text-03">
                    {agents.length ? (
                      <ul className="mt-1 flex flex-col gap-1">{agents.map((a) => <li key={a.id}><span className="text-text-05">{a.name}</span>{a.description ? ` · ${a.description}` : ""}</li>)}</ul>
                    ) : "None"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-text-05">{workspaceText("reviewRules")}</dt>
                  <dd className="text-text-03">
                    {rules.length ? `${rules.filter((r) => r.severity === "block").length} must, ${rules.filter((r) => r.severity === "warn").length} should` : "None"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-text-05">{workspaceText("workflows")}</dt>
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
