"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeSelect, NativeTextArea } from "@opal/components";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card, h1Class, pageClass } from "@/sections/sources/shared";
import { primary, REQUESTS_URL, secondary, send } from "@/sections/sources/integrations";

interface Req {
  id: string; kind: string; item_key: string; item_name: string; reason: string; state: string;
  decided_by_email: string | null; decision_note: string; created_at: string; decided_at: string | null;
}
interface Item { kind: string; key: string; name: string; description: string; why_approval: string; my_request: Req | null }
interface Discover { items: Item[]; my_requests: Req[] }

const STATE = new Map([
  ["pending", "Requested"],
  ["approved", "Approved"],
  ["declined", "Declined"],
  ["withdrawn", "Withdrawn"],
]);

function Status({ request, awaitingSetup = false }: { request: Req; awaitingSetup?: boolean }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  return (
    <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04" data-testid="request-state">
      {awaitingSetup
        ? workspaceText("workspaceRequest.awaitingSetupStatus")
        : STATE.get(request.state) ?? request.state}
    </span>
  );
}

/**
 * Discover: what this workspace supports but has not turned on, with a Request button for each. A request goes to the
 * administrators' Approvals page; approving it is a decision, and an administrator then sets the item up.
 */
export default function DiscoverPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const groups = [
    { kind: "connector", heading: workspaceText("workspaceSources"), note: "Company systems whose documents could be searched. You would only see what you can open there." },
    { kind: "skill", heading: workspaceText("packs"), note: workspaceText("discoverPacksAwaitingActivation") },
    { kind: "plugin", heading: workspaceText("tools"), note: "Tools that exist here but chat assistants may not use yet." },
  ];
  const requestKinds = new Map([
    ["connector", "Workspace source"],
    ["skill", workspaceText("pack")],
    ["plugin", workspaceText("tool")],
  ]);
  const { data, error, isLoading, mutate } = useSWR<Discover>(
    REQUESTS_URL,
    errorHandlingFetcher,
    {
      refreshInterval: (latest) => {
        const hasOpenRequest = latest?.items.some(({ my_request }) =>
          my_request?.state === "pending" || my_request?.state === "approved",
        );
        const hasPendingHistory = latest?.my_requests.some((request) => request.state === "pending");
        return hasOpenRequest || hasPendingHistory ? 10_000 : 0;
      },
    },
  );
  const loaded = data !== undefined;
  useEffect(() => {
    const target = window.location.hash.slice(1);
    if (loaded && target.startsWith("request-")) {
      document.getElementById(target)?.scrollIntoView({ block: "nearest" });
    }
  }, [loaded]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [asking, setAsking] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const searchTerm = query.trim().toLowerCase();
  const visibleGroups = groups
    .filter((group) => category === "all" || group.kind === category)
    .map((group) => ({
      ...group,
      items: (data?.items ?? []).filter(
        (item) => item.kind === group.kind &&
          `${item.name} ${item.description}`.toLowerCase().includes(searchTerm),
      ),
    }))
    .filter((group) => !searchTerm || group.items.length > 0);

  async function run(fn: () => Promise<string>) {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : workspaceText("couldNotSaveTryAgainInAMoment") });
    } finally {
      await mutate().catch(() => undefined);
      setBusy(false);
    }
  }

  return (
    <div className={pageClass} data-testid="discover-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>{workspaceText("discover")}</h1>
        <p className="text-sm text-text-03">{workspaceText("discoverRequestDescription")}</p>
      </header>
      {msg && <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-text-05" : "text-status-text-error-05"}`} data-testid="discover-message">{msg.text}</p>}
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loading")}</p>}
      {error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("discoverCouldNotBeLoadedTryAgainInA")}</p>}
      {data && (
        <ResponsiveLayout display="flex" className="flex-wrap items-end gap-3">
          <label className="flex min-w-40 flex-1 flex-col gap-1 text-sm font-medium text-text-05">
            {workspaceText("search")}
            <NativeInput
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3"
            />
          </label>
          <label className="flex min-w-36 flex-col gap-1 text-sm font-medium text-text-05">
            {workspaceText("category")}
            <NativeSelect
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3"
            >
              <option value="all">{workspaceText("all")}</option>
              {groups.map((group) => (
                <option key={group.kind} value={group.kind}>{group.heading}</option>
              ))}
            </NativeSelect>
          </label>
          {(query !== "" || category !== "all") && (
            <ActionButton
              type="button"
              className={secondary}
              onClick={() => { setQuery(""); setCategory("all"); }}
            >
              {workspaceText("clearFilters")}
            </ActionButton>
          )}
          {data.my_requests.length > 0 && (
            <NavLink href="/app/sources/discover#disc-mine" className="inline-flex min-h-11 items-center text-sm font-semibold text-text-05 underline">
              {workspaceText("yourRequests")}
            </NavLink>
          )}
        </ResponsiveLayout>
      )}
      {data && visibleGroups.length === 0 && (
        <p role="status" className="text-sm text-text-03">
          {workspaceText("noMatchingResultsTryAnotherQueryOrClearA")}
        </p>
      )}
      {data && visibleGroups.map((g) => {
        const { items } = g;
        return (
          <section key={g.kind} aria-labelledby={`disc-${g.kind}`} className="flex flex-col gap-2">
            <h2 id={`disc-${g.kind}`} className="text-xl font-semibold text-text-05">{g.heading}</h2>
            <p className="text-sm text-text-03">{g.note}</p>
            {items.length === 0 ? (
              <p className="text-sm text-text-03">{workspaceText("nothingMoreToAddHere")}</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {items.map((i) => {
                  const id = `${i.kind}:${i.key}`;
                  const awaitingSetup = i.my_request?.state === "approved";
                  const open = i.my_request?.state === "pending" || awaitingSetup;
                  return (
                    <li key={id} id={i.kind === "connector" ? `workspace-source-${i.key}` : undefined} className={`${card} flex flex-col gap-2`} data-testid="discover-item">
                      <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-2">
                        <h3 className="text-base font-semibold text-text-05">{i.name}</h3>
                        {i.my_request && <Status request={i.my_request} awaitingSetup={awaitingSetup} />}
                      </ResponsiveLayout>
                      {i.description && <p className="text-sm text-text-04">{i.description}</p>}
                      <p className="text-xs text-text-03">{i.why_approval}</p>
                      {i.my_request?.decision_note && (
                        <p className="whitespace-pre-wrap wrap-anywhere text-xs text-text-04">
                          {workspaceText("administratorSNote")} {i.my_request.decision_note}
                        </p>
                      )}
                      {!open && (asking === id ? (
                        <ResponsiveLayout display="flex" className="flex-col gap-2">
                          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("whyWouldItHelpOptional")}<NativeTextArea
                              className="min-h-20 rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05"
                              maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)}
                            />
                          </label>
                          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                            <ActionButton
                              type="button" className={primary} disabled={busy}
                              onClick={() => run(
                                // oxlint-disable-next-line react-doctor/no-impure-state-updater -- This callback is run by an event handler, outside React state updates.
                                async () => {
                                await send("POST", "/api/sources/requests", { kind: i.kind, item_key: i.key, reason });
                                setAsking(null);
                                setReason("");
                                return `Asked for ${i.name}. An administrator will decide; its status shows here.`;
                              })}
                            >{workspaceText("sendRequest")}</ActionButton>
                            <ActionButton type="button" className={secondary} disabled={busy} onClick={() => { setAsking(null); setReason(""); }}>{workspaceText("cancel")}</ActionButton>
                          </ResponsiveLayout>
                        </ResponsiveLayout>
                      ) : (
                          <div>
                            <ActionButton type="button" className={secondary} disabled={busy} onClick={() => { setAsking(id); setReason(""); setMsg(null); }} aria-label={`Request ${i.name}`}>
                              {i.my_request ? "Ask again" : "Request"}
                            </ActionButton>
                          </div>
                      ))}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        );
      })}
      {data && data.my_requests.length > 0 && (
        <section id="disc-mine" tabIndex={-1} className={card} aria-labelledby="disc-mine-heading" data-testid="my-requests">
          <h2 id="disc-mine-heading" className="text-base font-semibold text-text-05">{workspaceText("yourRequests")}</h2>
          <ul className="mt-2 flex flex-col divide-y divide-border-01">
            {data.my_requests.map((r) => (
              <li key={r.id} id={`request-${r.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span className="min-w-0 text-text-05">
                  {r.item_name} <span className="text-text-03">· {requestKinds.get(r.kind) ?? r.kind} · {new Date(r.created_at).toLocaleDateString()}</span>
                  {r.decision_note && <span className="block text-xs text-text-04">{workspaceText("note")}{" "}{r.decision_note}</span>}
                </span>
                <ResponsiveLayout as="span" display="flex" className="items-center gap-2">
                  <Status request={r} />
                  {r.state === "pending" && (
                    <ActionButton type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await send("POST", `/api/sources/requests/${r.id}/withdraw`); return `Withdrew the request for ${r.item_name}.`; })}>{workspaceText("withdraw")}</ActionButton>
                  )}
                </ResponsiveLayout>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
