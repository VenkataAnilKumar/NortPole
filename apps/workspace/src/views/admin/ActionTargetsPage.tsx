"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

const URL = "/api/admin/action-targets";
const CLASSES = ["public", "internal", "confidential", "restricted"] as const;

interface Target {
  id: number;
  name: string;
  url: string;
  kind?: string;
  tier?: string;
  allowed_data_classes: string[];
  enabled: boolean;
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const input = "min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

async function send(url: string, method: string, body: unknown): Promise<void> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `The change could not be saved (HTTP ${res.status}).`);
  }
}

function ClassPicker({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  return (
    <fieldset className="flex flex-wrap gap-3">
      <legend className="mb-1 text-sm font-medium text-text-05">Data classes this destination may receive</legend>
      {CLASSES.map((c) => (
        <label key={c} className="flex min-h-11 items-center gap-2 text-sm text-text-05">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={value.includes(c)}
            onChange={(e) => onChange(e.target.checked ? [...value, c] : value.filter((x) => x !== c))}
          />
          {c}
        </label>
      ))}
    </fieldset>
  );
}

/**
 * Where approved drafts may be sent. People pick from this list and cannot type
 * a destination. A draft is sent only if the workspace's data class is ticked
 * for the destination; the check runs again at send time.
 */
export default function ActionTargetsPage() {
  const { data, error, isLoading, mutate } = useSWR<Target[]>(URL, errorHandlingFetcher);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [kind, setKind] = useState<"webhook" | "email">("webhook");
  const [tier, setTier] = useState("act_with_approval");
  const [classes, setClasses] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
      await mutate();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "The change could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-8" data-testid="action-targets-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-text-05">Send destinations</h1>
        <p className="text-sm text-text-03">
          Where an approved draft may be sent. Addresses that point to link-local or cloud-metadata locations are refused.
          Leave all data classes unticked to keep a destination from receiving anything.
        </p>
      </header>

      <section className={card} aria-labelledby="new-target">
        <h2 id="new-target" className="mb-3 text-base font-semibold text-text-05">Add a destination</h2>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Name
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Type
            <select className={input} value={kind} onChange={(e) => { setKind(e.target.value as "webhook" | "email"); setUrl(""); }}>
              <option value="webhook">Web address (webhook)</option>
              <option value="email">Email (fixed recipients)</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            {kind === "email" ? "Recipients (people choosing this destination cannot change them)" : "Web address (https recommended)"}
            <input className={input} value={url} onChange={(e) => setUrl(e.target.value)} placeholder={kind === "email" ? "mailto:finance@example.com" : "https://example.com/hook"} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            How far the product may go
            <select className={input} value={tier} onChange={(e) => setTier(e.target.value)}>
              <option value="act_with_approval">Act with approval: prepare, approve the exact content, send</option>
              <option value="draft_only">Draft only: prepare and review, but never approve or send</option>
              <option value="read_only">Read only: nothing can be proposed</option>
            </select>
          </label>
          <ClassPicker value={classes} onChange={setClasses} />
          {message && <p role="alert" className="text-sm text-status-text-error-05">{message}</p>}
          <div>
            <button
              type="button"
              className={primary}
              disabled={busy || !name.trim() || !url.trim()}
              onClick={() =>
                run(async () => {
                  await send(URL, "POST", { name, kind, tier, url, allowed_data_classes: classes, enabled: true });
                  setName("");
                  setUrl("");
                  setClasses([]);
                })
              }
            >
              {busy ? "Saving…" : "Add destination"}
            </button>
          </div>
        </div>
      </section>

      {isLoading ? (
        <p className="text-sm text-text-03">Loading…</p>
      ) : error ? (
        <p role="alert" className="text-sm text-text-05">Destinations could not be loaded.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {(data ?? []).map((t) => (
            <li key={t.id} className={card} data-testid="target-item">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-text-05">{t.name}</h2>
                  <p className="truncate text-sm text-text-03">{t.kind === "email" ? "Email · " : ""}{t.url}</p>
                  {t.tier && t.tier !== "act_with_approval" && <p className="text-sm text-text-03" data-testid="tier-note">{t.tier === "read_only" ? "Read only" : "Draft only"}</p>}
                  <p className="text-sm text-text-03">
                    May receive: {t.allowed_data_classes.length ? t.allowed_data_classes.join(", ") : "nothing"}
                  </p>
                </div>
                <button
                  type="button"
                  className={secondary}
                  disabled={busy}
                  onClick={() => run(() => send(`${URL}/${t.id}`, "PATCH", { name: t.name, kind: t.kind ?? "webhook", tier: t.tier ?? "act_with_approval", url: t.url, allowed_data_classes: t.allowed_data_classes, enabled: !t.enabled }))}
                >
                  {t.enabled ? "Disable" : "Enable"}
                </button>
              </div>
              {!t.enabled && <p className="mt-2 text-xs text-text-03">Disabled: nothing can be sent here.</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
