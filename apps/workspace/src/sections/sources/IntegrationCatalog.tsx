"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card } from "@/sections/sources/shared";
import {
  CATALOG_URL,
  KIND_LABEL,
  REQUESTS_URL,
  categoryLabel,
  primary,
  secondary,
  send,
  type IntegrationItem,
} from "@/sections/sources/integrations";

interface Req { id: string; kind: string; item_key: string; state: string; decision_note: string }

const STATE_LABEL: Record<IntegrationItem["state"], string> = {
  available: "Available",
  needs_approval: "Needs approval",
  blocked: "Blocked",
  installed: "Installed",
  connected: "Connected",
};

type Type = "all" | "connector" | "plugin";

/** The reason a person can give an administrator, and the token field for connecting, live inside the card. */
function Card({ item, req, busy, run }: {
  item: IntegrationItem;
  req: Req | null;
  busy: boolean;
  run: (fn: () => Promise<string>) => void;
}) {
  const [form, setForm] = useState<"request" | "connect" | null>(null);
  const [reason, setReason] = useState("");
  const [token, setToken] = useState("");
  const base = `${CATALOG_URL}/${item.id}`;
  const pending = req?.state === "pending";
  const declined = req?.state === "declined";
  const stateLabel = item.state === "needs_approval" && pending ? "Requested" : STATE_LABEL[item.state];

  return (
    <div className={`${card} flex flex-col gap-2`} data-testid="integration-card" data-state={item.state}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-text-05">{item.name}</h3>
        <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04" data-testid="integration-state">
          {stateLabel}
        </span>
      </div>
      <p className="text-sm text-text-04">{item.description}</p>
      <p className="text-xs text-text-03">
        <span className="rounded-md bg-background-neutral-02 px-1.5 py-0.5 font-semibold uppercase tracking-wide">{KIND_LABEL[item.kind]}</span>{" "}
        {categoryLabel(item.category)}
      </p>
      <details className="text-xs text-text-03">
        <summary className="min-h-6 cursor-pointer font-medium text-text-04">What it can do</summary>
        <ul className="mt-1 flex flex-col gap-1">
          {item.actions.map((a) => (
            <li key={a.id}>
              <span className="font-medium text-text-05">{a.name}</span>{" "}
              <span className="rounded-md border border-border-02 px-1 text-[10px] uppercase">{a.effect === "write" ? "changes things" : "reads"}</span>
              <span className="block">{a.description}</span>
            </li>
          ))}
          <li>Talks only to {item.hosts.join(", ")}. {item.needs_account ? "Uses your own account there." : "Needs no account."}</li>
        </ul>
      </details>
      {item.update_available && <p className="text-xs text-text-04">A newer version ({item.version}) is available; you have {item.installed_version}.</p>}
      {declined && req?.decision_note && <p className="text-xs text-text-04">Administrator&apos;s note: {req.decision_note}</p>}
      {item.state === "blocked" && <p className="text-xs text-text-04">Your administrator has blocked this.</p>}

      {form === "request" && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Why would it help? (optional)
            <textarea className="min-h-20 rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primary} disabled={busy} onClick={() => run(async () => {
              await send("POST", "/api/sources/requests", { kind: item.kind, item_key: `integration:${item.id}`, reason });
              setForm(null); setReason("");
              return `Asked for ${item.name}. An administrator will decide; you will see the answer here and in your Inbox.`;
            })}>Send request</button>
            <button type="button" className={secondary} onClick={() => setForm(null)}>Cancel</button>
          </div>
        </div>
      )}
      {form === "connect" && (
        <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
          await send("PUT", `${base}/account`, item.needs_account ? { access_token: token } : {});
          setForm(null); setToken("");
          return `${item.name} is connected with your account.`;
        }); }}>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
            Your {item.name} access token
            <input type="password" autoComplete="off" className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05" value={token} onChange={(e) => setToken(e.target.value)} required />
          </label>
          <p className="text-xs text-text-03">Create a personal access token in {item.name}, with only the permissions you need. It is stored sealed, used only for your own calls, and never shown again.</p>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={primary} disabled={busy || token.length === 0}>Connect</button>
            <button type="button" className={secondary} onClick={() => { setForm(null); setToken(""); }}>Cancel</button>
          </div>
        </form>
      )}

      {form === null && (
        <div className="flex flex-wrap gap-2">
          {item.state === "available" && (
            <button type="button" className={primary} disabled={busy} aria-label={`Install ${item.name}`} onClick={() => run(async () => { await send("POST", `${base}/install`, {}); return `${item.name} installed${item.needs_account ? ". Connect your account to use it." : "."}`; })}>Install</button>
          )}
          {item.state === "needs_approval" && !pending && (
            <button type="button" className={secondary} disabled={busy} aria-label={`Request ${item.name}`} onClick={() => setForm("request")}>{declined ? "Ask again" : "Request"}</button>
          )}
          {item.state === "needs_approval" && pending && req && (
            <button type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await send("POST", `/api/sources/requests/${req.id}/withdraw`); return `Withdrew the request for ${item.name}.`; })}>Withdraw request</button>
          )}
          {item.state === "installed" && item.needs_account && (
            <button type="button" className={primary} disabled={busy} aria-label={`Connect my account to ${item.name}`} onClick={() => setForm("connect")}>Connect my account</button>
          )}
          {item.state === "connected" && (
            <button type="button" className={secondary} disabled={busy} aria-label={`Disconnect ${item.name}`} onClick={() => run(async () => { await send("DELETE", `${base}/account`); return `Disconnected ${item.name}.`; })}>Disconnect</button>
          )}
          {(item.state === "installed" || item.state === "connected") && (
            <button type="button" className={secondary} disabled={busy} aria-label={`Remove ${item.name}`} onClick={() => run(async () => { await send("DELETE", base); return `Removed ${item.name}.`; })}>Remove</button>
          )}
        </div>
      )}
    </div>
  );
}

/** A tile with the first letter, the way a directory shows a logo when there is none. */
function Tile({ name }: { name: string }) {
  return (
    <span aria-hidden="true" className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-border-02 bg-background-neutral-02 text-base font-semibold text-text-05">
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

/**
 * One directory row: tile, name with a check (every definition is a reviewed, signed one), a one-line description and
 * "Connector · category". It opens in place to the full card, where install, connect and request live; a plus on
 * hover installs what the person may install straight away.
 */
function Row({ item, req, busy, run }: {
  item: IntegrationItem; req: Req | null; busy: boolean; run: (fn: () => Promise<string>) => void;
}) {
  const [open, setOpen] = useState(false);
  const sub = `${KIND_LABEL[item.kind]} · ${categoryLabel(item.category)}`;
  const status = item.state === "installed" ? "Installed" : item.state === "connected" ? "Connected" : item.state === "blocked" ? "Blocked" : null;
  return (
    <li className="rounded-2xl border border-border-01 bg-background-neutral-00/60">
      <div className="group relative flex items-center gap-3 rounded-2xl px-3 py-3 hover:bg-background-tint-02">
        <button type="button" aria-expanded={open} aria-label={`${item.name}, ${sub}${status ? `, ${status}` : ""}`} onClick={() => setOpen(!open)} className="flex min-h-11 min-w-0 flex-1 items-center gap-3 text-left">
          <Tile name={item.name} />
          <span className="flex min-w-0 flex-col">
            <span className="flex items-center gap-1.5 text-base font-medium text-text-05">
              <span className="truncate">{item.name}</span>
              <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4 shrink-0 text-text-03" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="8" cy="8" r="6.2" /><path d="m5.4 8.2 1.8 1.8 3.4-3.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </span>
            <span className="truncate text-sm text-text-04">{item.description}</span>
            <span className="truncate text-xs text-text-03">{sub}{status ? ` · ${status}` : ""}</span>
          </span>
        </button>
        {(item.state === "installed" || item.state === "connected") && (
          <svg aria-label={status ?? ""} role="img" viewBox="0 0 16 16" className="mr-2 size-5 shrink-0 text-text-03" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="m3.5 8.5 3 3 6-6.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        )}
        {item.state === "available" && (
          <button type="button" disabled={busy} aria-label={`Install ${item.name} quickly`} onClick={() => run(async () => { await send("POST", `${CATALOG_URL}/${item.id}/install`, {}); return `${item.name} installed${item.needs_account ? ". Open it to connect your account." : "."}`; })} className="flex size-9 shrink-0 items-center justify-center rounded-lg text-xl text-text-05 border border-border-02 disabled:opacity-50">+</button>
        )}
      </div>
      {open && <div className="px-2 pb-3"><Card item={item} req={req} busy={busy} run={run} /></div>}
    </li>
  );
}

/**
 * The integration catalog: search it, narrow it by category and type, then install or connect
 * right on the card. What an administrator has not allowed yet shows Request instead; asking turns nothing on.
 */
export default function IntegrationCatalog() {
  const catalog = useSWR<{ items: IntegrationItem[] }>(CATALOG_URL, errorHandlingFetcher);
  const requests = useSWR<{ my_requests: Req[] }>(REQUESTS_URL, errorHandlingFetcher);
    const [category, setCategory] = useState("all");
  const [type, setType] = useState<Type>("all");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const run = (fn: () => Promise<string>) => {
    setBusy(true);
    setMsg(null);
    fn()
      .then(async (text) => { setMsg({ ok: true, text }); await Promise.all([catalog.mutate(), requests.mutate()]); })
      .catch((e: unknown) => setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." }))
      .finally(() => setBusy(false));
  };

  const items = useMemo(() => catalog.data?.items ?? [], [catalog.data]);
  const reqFor = (id: string): Req | null =>
    (requests.data?.my_requests ?? []).find((r) => r.item_key === `integration:${id}` && r.state !== "withdrawn") ?? null;

  const inShow = items;
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    inShow.forEach((i) => counts.set(i.category, (counts.get(i.category) ?? 0) + 1));
    return [...counts.entries()];
  }, [inShow]);
  const visible = inShow.filter((i) =>
    (category === "all" || i.category === category) &&
    (type === "all" || i.kind === type) &&
    (q.trim() === "" || `${i.name} ${i.description} ${i.category}`.toLowerCase().includes(q.trim().toLowerCase())));

  const chip = (active: boolean) =>
    `min-h-11 rounded-full border px-3 text-sm font-medium ${active ? "border-text-05 bg-text-05 text-background-neutral-00" : "border-border-02 text-text-04"}`;

  return (
    <section aria-labelledby="catalog-title" className="flex flex-col gap-4" data-testid="integration-catalog">
      <div className="flex flex-col gap-1">
        <h2 id="catalog-title" className="text-xl font-semibold text-text-05">Catalog</h2>
        <p className="text-sm text-text-03">Search what is on offer and install or connect it here. Anything your administrator has not allowed yet shows Request instead.</p>
      </div>
      <div className={`${card} flex flex-col gap-3`}>
        <label className="flex flex-col gap-1 text-sm font-medium text-text-05">
          <span className="sr-only">Search</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search connectors and plugins" className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05" />
        </label>
        <div role="group" aria-label="Show" className="flex flex-wrap items-center gap-2">
          {(["all", "connector", "plugin"] as Type[]).map((t) => (
            <button key={t} type="button" aria-pressed={type === t} className={chip(type === t)} onClick={() => setType(t)}>
              {t === "all" ? "All" : `${KIND_LABEL[t]}s`}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Category" className="flex flex-wrap gap-1" data-testid="catalog-categories">
          <button type="button" aria-pressed={category === "all"} className={`min-h-11 rounded-xl px-3 text-sm ${category === "all" ? "bg-background-neutral-02 font-semibold text-text-05" : "text-text-03 hover:text-text-05"}`} onClick={() => setCategory("all")}>All categories</button>
          {categories.map(([c, n]) => (
            <button key={c} type="button" aria-pressed={category === c} className={`min-h-11 rounded-xl px-3 text-sm ${category === c ? "bg-background-neutral-02 font-semibold text-text-05" : "text-text-03 hover:text-text-05"}`} onClick={() => setCategory(c)}>
              {categoryLabel(c)} <span className="text-xs opacity-70">{n}</span>
            </button>
          ))}
        </div>
      </div>
      <p role={msg?.ok === false ? "alert" : "status"} className={`min-h-5 text-sm ${msg?.ok === false ? "text-status-text-error-05" : "text-text-05"}`} data-testid="integration-message">{msg?.text ?? ""}</p>
      {catalog.isLoading && <p className="text-sm text-text-03">Loading the catalog…</p>}
      {catalog.error && <p role="alert" className="text-sm text-status-text-error-05">The catalog could not be loaded. Try again in a moment.</p>}
      {catalog.data && visible.length === 0 && (
        <p className="text-sm text-text-03" data-testid="integration-empty">{items.length === 0 ? "Nothing is on offer yet. An administrator adds integrations to this workspace." : "Nothing matches. Try another search or category."}</p>
      )}
      {visible.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2" data-testid="integration-list">
          {visible.map((i) => (
            <Row key={i.id} item={i} req={reqFor(i.id)} busy={busy} run={run} />
          ))}
        </ul>
      )}
    </section>
  );
}
