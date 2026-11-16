"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card } from "@/sections/sources/shared";
import { CATALOG_URL, KIND_LABEL, categoryLabel, secondary, send, type IntegrationItem } from "@/sections/sources/integrations";

/**
 * What the person has installed of one kind (connectors or plugins), with Disconnect and Remove. Installing and
 * connecting happen in the Discover catalog; this list is the person's own.
 */
export default function InstalledIntegrations({ kind }: { kind: "connector" | "plugin" }) {
  const { data, error, mutate } = useSWR<{ items: IntegrationItem[] }>(`${CATALOG_URL}?kind=${kind}`, errorHandlingFetcher);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const mine = (data?.items ?? []).filter((i) => i.state === "installed" || i.state === "connected");
  const label = `${KIND_LABEL[kind]}s`;

  const act = async (fn: () => Promise<void>, done: string) => {
    setBusy(true);
    try { await fn(); setMsg(done); await mutate(); } catch (e) { setMsg(e instanceof Error ? e.message : "The request failed."); } finally { setBusy(false); }
  };

  return (
    <section className={card} aria-labelledby={`mine-${kind}`} data-testid={`installed-${kind}`}>
      <h2 id={`mine-${kind}`} className="text-base font-semibold text-text-05">Your {label.toLowerCase()}</h2>
      {error && <p role="alert" className="mt-1 text-sm text-status-text-error-05">Your {label.toLowerCase()} could not be loaded.</p>}
      {data && mine.length === 0 && (
        <p className="mt-1 text-sm text-text-03">Nothing installed yet. Find {label.toLowerCase()} in <Link href="/app/sources/discover" className="font-semibold text-text-05 underline">Discover</Link> and install or connect them there.</p>
      )}
      {mine.length > 0 && (
        <ul className="mt-2 flex flex-col divide-y divide-border-01">
          {mine.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm" data-testid="installed-item">
              <span className="min-w-0">
                <span className="font-medium text-text-05">{i.name}</span>
                <span className="block text-xs text-text-03">{categoryLabel(i.category)} · {i.state === "connected" ? "Connected with your account" : i.needs_account ? "Installed; connect your account in Discover to use it" : "Installed"}</span>
              </span>
              <span className="flex flex-wrap gap-2">
                {i.state === "connected" && <button type="button" className={secondary} disabled={busy} aria-label={`Disconnect ${i.name}`} onClick={() => act(() => send("DELETE", `${CATALOG_URL}/${i.id}/account`), `Disconnected ${i.name}.`)}>Disconnect</button>}
                <button type="button" className={secondary} disabled={busy} aria-label={`Remove ${i.name}`} onClick={() => act(() => send("DELETE", `${CATALOG_URL}/${i.id}`), `Removed ${i.name}.`)}>Remove</button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {msg && <p role="status" className="mt-2 text-sm text-text-04">{msg}</p>}
    </section>
  );
}
