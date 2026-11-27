"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import ExtensionRules from "@/views/admin/ExtensionRules";

interface Item {
  kind: string;
  name: string;
  detail: string;
  status: string;
  owner: string | null;
  version: string | null;
  last_use: string | null;
  uses: number | null;
  notes: string[];
}
interface Inventory {
  generated_at: string;
  items: Item[];
  counts: Record<string, number>;
  limits: string[];
}

const SECTIONS: { kind: string; title: string }[] = [
  { kind: "pack", title: "Packs (active versions)" },
  { kind: "destination", title: "Send destinations" },
  { kind: "model_route", title: "Model routes" },
  { kind: "skill", title: "Skills" },
  { kind: "mcp_server", title: "MCP servers" },
];
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";

function lastUse(i: Item): string {
  if (!i.last_use || i.last_use === "not recorded") return "not recorded";
  const d = new Date(i.last_use);
  return Number.isNaN(d.getTime()) ? i.last_use : d.toLocaleString();
}

/** What is active in this workspace, in one read-only list. Nothing here can be changed. */
export default function InventoryPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, error, isLoading } = useSWR<Inventory>("/api/admin/inventory", errorHandlingFetcher);
  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-6xl flex-col gap-6 p-4 sm:p-8" data-testid="inventory-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("inventory")}</h1>
        <p className="mt-1 text-sm text-text-03">{workspaceText("everythingActiveInThisWorkspacePacksSendDestinationsModel")}</p>
      </div>
      <ExtensionRules />
      {error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("couldNotLoadTheInventory")}</p>}
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loading")}</p>}
      {data &&
        SECTIONS.map(({ kind, title }) => {
          const rows = data.items.filter((i) => i.kind === kind);
          return (
            <section key={kind} className={card} aria-labelledby={`inv-${kind}`} data-testid={`inv-${kind}`}>
              <h2 id={`inv-${kind}`} className="text-base font-semibold text-text-05">
                {title} <span className="font-normal text-text-03">({rows.length})</span>
              </h2>
              {rows.length === 0 ? (
                <p className="mt-2 text-sm text-text-03">{workspaceText("none")}</p>
              ) : (
                <ul className="mt-3 flex flex-col divide-y divide-border-01">
                  {rows.map((i) => (
                    <li key={`${i.kind}-${i.name}-${i.version ?? ""}`} className="py-3" data-testid="inv-item">
                      <ResponsiveLayout display="flex" className="flex-wrap items-baseline justify-between gap-2">
                        <div className="min-w-0">
                          <span className="text-sm font-semibold text-text-05">{i.name}</span>
                          {i.version && <span className="ml-2 text-xs text-text-03">{i.version}</span>}
                          <span className="ml-2 text-xs text-text-03">{i.detail}</span>
                        </div>
                        <span className="rounded-full bg-background-neutral-02 px-2 py-0.5 text-xs font-medium text-text-05">{i.status}</span>
                      </ResponsiveLayout>
                      <p className="mt-1 text-xs text-text-03">{workspaceText("lastUse")}{" "}{lastUse(i)}
                        {i.uses !== null && i.uses !== undefined ? ` · ${i.uses} recorded use${i.uses === 1 ? "" : "s"}` : ""}
                        {i.notes.length ? ` · ${i.notes.join(" · ")}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      {data && (
        <ul className="list-disc pl-5 text-xs text-text-03">
          {data.limits.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
    </ResponsiveLayout>
  );
}
