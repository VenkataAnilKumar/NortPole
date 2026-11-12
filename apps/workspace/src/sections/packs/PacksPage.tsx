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
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

/**
 * Packs: bundles of task templates for one line of work. Picking a template
 * makes a draft task you can edit; nothing runs until you press Start, and the
 * pack only runs on the model routes and data classes it lists.
 */
export default function PacksPage() {
  const router = useRouter();
  const { data, error, isLoading } = useSWR<Pack[]>("/api/packs", errorHandlingFetcher);
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
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
      router.push("/app/reviewed-tasks");
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "Could not create the draft.");
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-8" data-testid="packs-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Packs</h1>
        <p className="text-sm text-text-03">
          Ready-made task templates for a line of work. Choosing one creates a draft for you to edit; nothing runs
          until you press Start.
        </p>
      </header>
      {failed && <p role="alert" className="text-sm text-status-error-05">{failed}</p>}

      {isLoading ? (
        <p className="text-sm text-text-03">Loading…</p>
      ) : error ? (
        <p role="alert" className="text-sm text-text-05">Packs could not be loaded.</p>
      ) : packs.length === 0 ? (
        <section className={card}>
          <h2 className="mb-1 text-base font-semibold text-text-05">No packs are active</h2>
          <p className="text-sm text-text-03">An administrator installs and activates signed packs. Until then, write your own task under Reviewed tasks.</p>
        </section>
      ) : (
        <ul className="flex flex-col gap-4">
          {packs.map((p) => (
            <li key={p.pack_id} className={card} data-testid="pack-card">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="text-lg font-semibold text-text-05">{p.name}</h2>
                  <p className="text-xs text-text-03">{p.vertical} · version {p.version}</p>
                </div>
              </div>
              {p.description && <p className="mt-2 text-sm text-text-03">{p.description}</p>}
              <p className="mt-2 text-xs text-text-03">
                Runs on {p.route_kinds.join(" or ")} model routes, for {p.data_classes.join(", ")} data.
                {p.requests_send_destinations ? " This pack asks to send results to a destination; an administrator decides whether that is allowed." : ""}
              </p>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {p.templates.map((t) => (
                  <li key={t.id} className="flex flex-col justify-between gap-2 rounded-xl border border-border-01 p-3">
                    <div>
                      <div className="text-sm font-semibold text-text-05">{t.title}</div>
                      <div className="mt-1 text-xs text-text-03">{t.request}</div>
                    </div>
                    <button type="button" className={secondary} disabled={!!busy} onClick={() => use(p, t)}>
                      {busy === `${p.pack_id}/${t.id}` ? "Creating…" : "Use this template"}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
