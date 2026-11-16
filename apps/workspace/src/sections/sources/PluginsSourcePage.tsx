"use client";

import Link from "next/link";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { useSettings } from "@/lib/settings/hooks";
import { card, h1Class, pageClass } from "@/sections/sources/shared";
import InstalledIntegrations from "@/sections/sources/InstalledIntegrations";

interface Kind { kind: string; label: string; on: boolean }
interface Tool { name: string; kind_label: string; allowed: boolean; mine: boolean }

/**
 * Plugins: the tools chat assistants may use in this workspace, and which are allowed. Administrators decide in the
 * tool catalog; a tool that is not allowed is never offered to the model. Drafts use no tools.
 */
export default function PluginsSourcePage() {
  const { data, error, isLoading } = useSWR<{ kinds: Kind[]; tools: Tool[] }>("/api/tool-catalog", errorHandlingFetcher);
  const craft = useSettings().nortpole_craft_enabled === true;
  const tools = [...(data?.tools ?? [])].sort((a, b) => Number(b.allowed) - Number(a.allowed) || a.name.localeCompare(b.name));

  return (
    <div className={pageClass} data-testid="plugins-source-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>Plugins</h1>
        <p className="text-sm text-text-03">
          Tools chat assistants may use here. A tool that is not allowed is never offered to an assistant. Drafts use no tools. Administrators decide what is allowed.
        </p>
        {craft && (
          <p className="text-sm text-text-03">
            <Link href="/app/plugins" className="font-semibold text-text-05 underline">Manage your own plugins</Link>
          </p>
        )}
      </header>
      <InstalledIntegrations kind="plugin" />
      {isLoading && <p className="text-sm text-text-03">Loading plugins…</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">Plugins could not be loaded. Try again in a moment.</p>}
      {data && (
        <>
          <section className={card} aria-labelledby="pl-kinds">
            <h2 id="pl-kinds" className="text-base font-semibold text-text-05">Kinds of tool</h2>
            <ul className="mt-2 flex flex-col gap-1">
              {data.kinds.map((k) => (
                <li key={k.kind} className="flex flex-wrap justify-between gap-2 text-sm" data-testid="pl-kind">
                  <span className="text-text-05">{k.label}</span>
                  <span className={k.on ? "text-text-05" : "text-text-03"}>{k.on ? "Allowed" : "Not allowed"}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className={card} aria-labelledby="pl-tools">
            <h2 id="pl-tools" className="text-base font-semibold text-text-05">Tools</h2>
            {tools.length === 0 ? (
              <p className="mt-1 text-sm text-text-03">No tools are set up.</p>
            ) : (
              <ul className="mt-2 flex flex-col divide-y divide-border-01">
                {tools.map((t, i) => (
                  <li key={`${t.name}-${i}`} className="flex flex-wrap items-baseline justify-between gap-2 py-2 text-sm" data-testid="pl-tool">
                    <span className="min-w-0">
                      <span className="font-medium text-text-05">{t.name}</span>
                      <span className="block text-xs text-text-03">{t.kind_label}{t.mine ? " · added by you" : ""}</span>
                    </span>
                    <span className={t.allowed ? "text-text-05" : "text-text-03"}>{t.allowed ? "Allowed" : "Not allowed"}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
