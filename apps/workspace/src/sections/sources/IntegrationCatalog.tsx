"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeSelect, NativeTextArea } from "@opal/components";
import { loadPage } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { Button } from "@opal/components";
import { useNavigation } from "@opal/navigation";
import { type Route } from "next";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { getSourceMetadata, isValidSource, listSourceMetadata } from "@/lib/connectors/utils";
import { SourceCategory, type SourceMetadata, type ValidSources } from "@/lib/connectors/types/source";
import { SOURCE_DESCRIPTION_KEYS } from "@/lib/connectors/constants";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { card, titleCase } from "@/sections/sources/shared";
import { createCustomSkillFromEditor, isSkillNameConflict } from "@/lib/skills/api";
import type { SkillsList } from "@/lib/skills/types";
import { SWR_KEYS } from "@/lib/swr-keys";
import {
  CATALOG_URL,
  REQUESTS_URL,
  categoryLabel,
  primary,
  secondary,
  send,
  type IntegrationItem,
  type WorkspaceIndexing,
} from "@/sections/sources/integrations";

interface Req {
  id: string;
  kind: string;
  item_key: string;
  state: string;
  decision_note: string;
}

const STATE_LABEL: Record<IntegrationItem["state"], string> = {
  available: "Available",
  needs_approval: "Needs approval",
  blocked: "Blocked",
  installed: "Installed",
  connected: "Connected",
};

interface WorkspaceSource {
  key: string;
  name: string;
  description: string;
  requestable: boolean;
  my_request?: Req | null;
  metadata?: SourceMetadata;
}

interface DirectoryEntry {
  id: string;
  name: string;
  description: string;
  category: string;
  integration?: IntegrationItem;
  workspace?: WorkspaceSource;
}

type WorkspaceStatus = {
  enabled: boolean;
  canConnect: boolean;
  canMonitor: boolean;
  configured: ReadonlySet<string>;
  indexing: ReadonlyMap<string, WorkspaceIndexing>;
};

function integrationId(source: string) {
  return source.replaceAll("_", "-");
}

function workspaceRequestState(request?: Req | null) {
  const state = request?.state;
  return state === "pending" || state === "approved" || state === "declined" ? state : null;
}

function WorkspaceAction({ source, status, busy, run }: {
  source: WorkspaceSource;
  status: WorkspaceStatus;
  busy: boolean;
  run: (fn: () => Promise<string>) => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const navigation = useNavigation();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const isConfigured = status.configured.has(source.key);
  const indexing = status.indexing.get(source.key);
  const adminUrl = source.metadata?.adminUrl;
  const requestState = workspaceRequestState(source.my_request);
  const canConnect = status.canConnect && Boolean(adminUrl);
  const canRequest = status.enabled && !isConfigured && !canConnect &&
    source.requestable && requestState !== "pending" && requestState !== "approved";

  return (
    <section className="flex flex-col items-start gap-2" aria-label={workspaceText("workspaceIndexing")}>
      <h4 className="text-sm font-semibold text-text-05">{workspaceText("workspaceIndexing")}</h4>
      <p className="text-sm text-text-03">
        {source.description}
      </p>
      {status.enabled && isConfigured && (
        <p role="status" className="text-sm font-medium text-text-05">
          {indexing && indexing.state !== "configured"
            ? workspaceText(`workspaceReadiness.${indexing.state}`)
            : workspaceText("workspaceConfigured")}
        </p>
      )}
      {requestState && (
        <div className="space-y-1 text-sm text-text-03">
          <p role="status" className="font-medium text-text-05">
            {workspaceText(`workspaceRequest.${requestState}`)}
          </p>
          {requestState === "approved" && !isConfigured && (
            <p>{workspaceText("workspaceRequest.awaitingSetup")}</p>
          )}
          {source.my_request?.decision_note && (
            <p className="whitespace-pre-wrap wrap-anywhere">{source.my_request.decision_note}</p>
          )}
        </div>
      )}
      {!status.enabled ? (
        <p className="text-xs text-text-03">{workspaceText("documentSearchMustBeEnabledToIndexThisSource")}</p>
      ) : canConnect && !isConfigured ? (
        <Button prominence="secondary" {...navigation.linkTo(adminUrl as Route)}>{workspaceText("indexForKnowledge")}</Button>
      ) : isConfigured ? (
        <ResponsiveLayout display="flex" className="flex-wrap gap-2">
          {(!indexing || indexing.hasIndexedDocuments) && (
            <Button
              prominence="secondary"
              {...navigation.linkTo(`/app/knowledge?source=${encodeURIComponent(source.key)}`)}
            >{workspaceText("viewKnowledge")}</Button>
          )}
          {status.canMonitor && (
            <Button prominence="secondary" {...navigation.linkTo(ADMIN_ROUTES.INDEXING_STATUS.path)}>{workspaceText("indexingStatus")}</Button>
          )}
        </ResponsiveLayout>
      ) : !source.requestable && !requestState ? (
        <p className="text-xs text-text-03">{workspaceText("workspaceSetupByAdmin")}</p>
      ) : null}
      {canRequest && (
        asking ? (
          <form className="w-full space-y-2" onSubmit={(event) => {
            event.preventDefault();
            if (busy) return;
            run(async () => {
              await send("POST", "/api/sources/requests", { kind: "connector", item_key: source.key, reason });
              setAsking(false);
              setReason("");
              return workspaceText("workspaceRequest.sent");
            });
          }}>
            <label className="block space-y-1 text-sm text-text-04">
              <span>{workspaceText("whyWouldItHelpOptional")}</span>
              <NativeTextArea
                className="block min-h-20 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2"
                maxLength={500}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <ResponsiveLayout display="flex" className="flex-wrap gap-2">
              <Button type="submit" disabled={busy}>{workspaceText("sendRequest")}</Button>
              <Button type="button" prominence="secondary" disabled={busy} onClick={() => setAsking(false)}>
                {workspaceText("cancel")}
              </Button>
            </ResponsiveLayout>
          </form>
        ) : (
          <Button type="button" prominence="secondary" disabled={busy} onClick={() => setAsking(true)}>
            {workspaceText(requestState === "declined" ? "workspaceRequest.again" : "requestWorkspaceSetup")}
          </Button>
        )
      )}
    </section>
  );
}

/** Skills the integration suggests: each has an Add button that creates it as the person's own skill. */
function SuggestedSkills({ item }: { item: IntegrationItem }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, mutate } = useSWR<SkillsList>(SWR_KEYS.userSkills, errorHandlingFetcher);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const have = new Set((data?.customs ?? []).filter((s) => s.user_permission === "OWNER").map((s) => s.name));
  const add = async (k: IntegrationItem["skills"][number]) => {
    setBusy(k.name);
    setMsg(null);
    try {
      await createCustomSkillFromEditor({ name: k.name, description: k.description, instructions_markdown: k.content, auto_enable: true });
      setMsg(`Added ${k.name} to your skills.`);
      await mutate();
    } catch (e) {
      setMsg(isSkillNameConflict(e) ? `You already have ${k.name}.` : e instanceof Error ? e.message : "The skill could not be added.");
    } finally {
      setBusy(null);
    }
  };
  return (
    <ResponsiveLayout display="flex" className="flex-col gap-1 text-xs text-text-03" data-testid="suggested-skills">
      <span className="font-medium text-text-04">{workspaceText("suggestedSkills")}</span>
      <ul className="flex flex-col gap-2">
        {item.skills.map((k) => (
          <li key={k.name} className="flex flex-wrap items-center justify-between gap-2">
            <span className="min-w-0"><span className="font-medium text-text-05">{k.name}</span><span className="block">{k.description}</span></span>
            <ActionButton type="button" className={secondary} disabled={busy !== null || have.has(k.name)} aria-label={`Add skill ${k.name}`} onClick={() => void add(k)}>{have.has(k.name) ? "Added" : busy === k.name ? "Adding…" : "Add"}</ActionButton>
          </li>
        ))}
      </ul>
      {msg && <span role="status" className="text-text-05">{msg}</span>}
    </ResponsiveLayout>
  );
}

/** The reason a person can give an administrator, and the token field for connecting, live inside the card. */
function Card({
  item,
  req,
  busy,
  run,
}: {
  item: IntegrationItem;
  req: Req | null;
  busy: boolean;
  run: (fn: () => Promise<string>) => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [form, setForm] = useState<"request" | "connect" | null>(null);
  const [reason, setReason] = useState("");
  const [token, setToken] = useState("");
  const base = `${CATALOG_URL}/${item.id}`;
  const pending = req?.state === "pending";
  const declined = req?.state === "declined";
  const stateLabel =
    item.state === "needs_approval" && pending ? "Requested" : STATE_LABEL[item.state];

  return (
    <ResponsiveLayout display="flex" className="flex-col gap-2" data-testid="integration-card" data-state={item.state}>
      <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-text-05">
          {item.needs_account ? "Personal account" : "Use in assistants"}
        </h4>
        <span
          className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs font-medium text-text-04"
          data-testid="integration-state"
        >
          {stateLabel}
        </span>
      </ResponsiveLayout>
      <p className="text-sm text-text-04">{item.description}</p>
      <details className="text-xs text-text-03">
        <summary className="min-h-6 cursor-pointer font-medium text-text-04">{workspaceText("whatItCanDo")}</summary>
        <ul className="mt-1 flex flex-col gap-1">
          {item.actions.map((a) => (
            <li key={a.id}>
              <span className="font-medium text-text-05">{a.name}</span>{" "}
              <span className="rounded-md border border-border-02 px-1 text-[10px] uppercase">{a.effect === "write" ? "changes things" : "reads"}</span>
              <span className="block">{a.description}</span>
            </li>
          ))}
          <li>{workspaceText("talksOnlyTo")}{" "}{item.hosts.join(", ")}. {item.needs_account ? "Uses your own account there." : "Needs no account."}</li>
          {item.actions.length > 0 && <li>{workspaceText("onceInstalled")}{item.needs_account ? " and connected" : ""}{workspaceText("yourChatsCanUseTheActionsThatOnlyRead")}</li>}
        </ul>
      </details>
      {item.skills.length > 0 && <SuggestedSkills item={item} />}
      {item.update_available && <p className="text-xs text-text-04">{workspaceText("aNewerVersion")}{item.version}{workspaceText("isAvailableYouHave")}{" "}{item.installed_version}.</p>}
      {declined && req?.decision_note && <p className="text-xs text-text-04">{workspaceText("administratorSNote")}{" "}{req.decision_note}</p>}
      {item.state === "blocked" && <p className="text-xs text-text-04">{workspaceText("yourAdministratorHasBlockedThis")}</p>}

      {form === "request" && (
        <ResponsiveLayout display="flex" className="flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("whyWouldItHelpOptional")}<NativeTextArea className="min-h-20 rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
            <ActionButton type="button" className={primary} disabled={busy} onClick={() => run(async () => {
              await send("POST", "/api/sources/requests", { kind: item.kind, item_key: `integration:${item.id}`, reason });
              setForm(null); setReason("");
              return `Asked for ${item.name}. An administrator will decide; you will see the answer here and in your Inbox.`;
            })}>{workspaceText("sendRequest")}</ActionButton>
            <ActionButton type="button" className={secondary} onClick={() => setForm(null)}>{workspaceText("cancel")}</ActionButton>
          </ResponsiveLayout>
        </ResponsiveLayout>
      )}
      {form === "connect" && (
        <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
          await send("PUT", `${base}/account`, item.auth_mode === "api_key" ? { api_key: token } : item.needs_account ? { access_token: token } : {});
          setForm(null); setToken("");
          return `${item.name} is connected with your account.`;
        }); }}>
          <label className="flex flex-col gap-1 text-sm font-medium text-text-05">{workspaceText("your")}{" "}{item.name} {item.auth_mode === "api_key" ? "API key" : "access token"}
            <NativeInput type="password" autoComplete="off" className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05" value={token} onChange={(e) => setToken(e.target.value)} required />
          </label>
          <p className="text-xs text-text-03">{workspaceText("create")}{" "}{item.auth_mode === "api_key" ? "an API key" : "a personal access token"} in {item.name}{workspaceText("withOnlyThePermissionsYouNeedItIsStored")}</p>
          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
            <ActionButton type="submit" className={primary} disabled={busy || token.length === 0}>{workspaceText("connect")}</ActionButton>
            <ActionButton type="button" className={secondary} onClick={() => { setForm(null); setToken(""); }}>{workspaceText("cancel")}</ActionButton>
          </ResponsiveLayout>
        </form>
      )}

      {form === null && (
        <ResponsiveLayout display="flex" className="flex-wrap gap-2">
          {item.state === "available" && (
            <ActionButton type="button" className={primary} disabled={busy} aria-label={`Install ${item.name}`} onClick={() => run(async () => { await send("POST", `${base}/install`, {}); return `${item.name} installed${item.needs_account ? ". Connect your account to use it." : "."}`; })}>{item.needs_account ? "Install" : "Use in assistants"}</ActionButton>
          )}
          {item.state === "needs_approval" && !pending && (
            <ActionButton type="button" className={secondary} disabled={busy} aria-label={`Request ${item.name}`} onClick={() => setForm("request")}>{declined ? "Ask again" : "Request"}</ActionButton>
          )}
          {item.state === "needs_approval" && pending && req && (
            <ActionButton type="button" className={secondary} disabled={busy} onClick={() => run(async () => { await send("POST", `/api/sources/requests/${req.id}/withdraw`); return `Withdrew the request for ${item.name}.`; })}>{workspaceText("withdrawRequest")}</ActionButton>
          )}
          {item.state === "installed" && item.needs_account && item.oauth_available && (
            <ActionButton type="button" className={primary} disabled={busy} aria-label={`Sign in with ${item.name}`} onClick={() => run(async () => {
              const res = await fetch(`${base}/oauth/start`, { method: "POST" });
              const data = await res.json().catch(() => null);
              if (!res.ok || typeof data?.authorize_url !== "string") throw new Error(typeof data?.detail === "string" ? data.detail : "Signing in could not be started.");
              loadPage(data.authorize_url);
              return `Opening ${item.name} to sign in…`;
            })}>{workspaceText("signInWith")}{" "}{item.name}</ActionButton>
          )}
          {item.state === "installed" && item.needs_account && (
            <ActionButton type="button" className={item.oauth_available ? secondary : primary} disabled={busy} aria-label={`Connect my account to ${item.name}`} onClick={() => setForm("connect")}>{item.oauth_available ? "Use a token instead" : "Connect my account"}</ActionButton>
          )}
          {item.state === "connected" && (
            <ActionButton type="button" className={secondary} disabled={busy} aria-label={`Disconnect ${item.name}`} onClick={() => run(async () => { await send("DELETE", `${base}/account`); return `Disconnected ${item.name}.`; })}>{workspaceText("disconnect")}</ActionButton>
          )}
          {(item.state === "installed" || item.state === "connected") && (
            <ActionButton type="button" className={secondary} disabled={busy} aria-label={`Remove ${item.name}`} onClick={() => run(async () => { await send("DELETE", base); return `Removed ${item.name}.`; })}>{workspaceText("remove")}</ActionButton>
          )}
        </ResponsiveLayout>
      )}
    </ResponsiveLayout>
  );
}

/** The service's logo, drawn in the page's text colour so it works in light and dark; a letter when there is none. */
const LOGOS = new Set([
  "airtable",
  "dropbox",
  "github",
  "gmail",
  "google-calendar",
  "google-drive",
  "hubspot",
  "notion",
  "slack",
  "spotify",
  "stripe",
  "webflow",
  "wikipedia",
]);

function Tile({ id, name, icon: Icon }: { id: string; name: string; icon?: SourceMetadata["icon"] }) {
  return (
    <ResponsiveLayout as="span" display="flex" aria-hidden="true" className="size-10 shrink-0 items-center justify-center rounded-xl border border-border-02 bg-background-neutral-02 text-base font-semibold text-text-05">
      {Icon ? <Icon size={20} /> : LOGOS.has(id) ? (
        <span
          className="block size-5 bg-text-05"
          style={{ WebkitMask: `url(/integration-logos/${id}.svg) center / contain no-repeat`, mask: `url(/integration-logos/${id}.svg) center / contain no-repeat` }}
        />
      ) : (
        name.slice(0, 1).toUpperCase()
      )}
    </ResponsiveLayout>
  );
}

function Row({
  entry,
  workspaceStatus,
  open,
  onToggle,
  req,
  busy,
  run,
}: {
  entry: DirectoryEntry;
  workspaceStatus: WorkspaceStatus;
  open: boolean;
  onToggle: () => void;
  req: Req | null;
  busy: boolean;
  run: (fn: () => Promise<string>) => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { integration: item, workspace } = entry;
  const indexing = workspace && workspaceStatus.indexing.get(workspace.key);
  const requestState = workspaceRequestState(workspace?.my_request);
  const workspaceSetup = workspace && workspaceStatus.enabled && (
    indexing && indexing.state !== "configured"
      ? workspaceText(`workspaceReadiness.${indexing.state}`)
      : workspaceStatus.configured.has(workspace.key)
      ? workspaceText("workspaceConfigured")
      : requestState
        ? workspaceText(requestState === "approved" ? "workspaceRequest.awaitingSetupStatus" : `workspaceRequest.${requestState}`)
      : workspaceStatus.canConnect || !workspace.requestable
        ? workspaceText("workspaceSetupByAdmin")
        : workspaceText("requestWorkspaceSetup")
  );
  const sub = [
    workspace && workspaceText("workspaceIndexing"),
    workspaceSetup,
    item && (item.needs_account ? "Personal account" : "Assistant actions"),
  ]
    .filter(Boolean)
    .join(" · ");
  const status =
    item?.state === "connected"
      ? "Account connected"
      : item?.state === "installed"
        ? "Installed"
        : item?.state === "blocked"
          ? "Assistant use blocked"
          : null;
  return (
    <li data-workspace-source={workspace?.key}>
      <ResponsiveLayout display="flex" className="group relative items-center gap-3 rounded-xl px-1 py-3 hover:bg-background-tint-02">
        <ActionButton
          type="button"
          aria-expanded={open}
          aria-label={`${entry.name}, ${sub}${status ? `, ${status}` : ""}`}
          onClick={onToggle}
          className="flex min-h-11 min-w-0 flex-1 items-center gap-3 text-left"
        >
          <Tile id={entry.id} name={entry.name} icon={workspace?.metadata?.icon} />
          <ResponsiveLayout as="span" display="flex" className="min-w-0 flex-col">
            <ResponsiveLayout as="span" display="flex" className="items-center gap-1.5 text-base font-medium text-text-05">
              <span className="truncate">{entry.name}</span>
            </ResponsiveLayout>
            <span className="truncate text-sm text-text-04">{entry.description}</span>
            <span className="truncate text-xs text-text-03">
              {sub}
              {status ? ` · ${status}` : ""}
            </span>
          </ResponsiveLayout>
        </ActionButton>
        {(item?.state === "installed" || item?.state === "connected") && (
          <svg
            aria-label={status ?? ""}
            role="img"
            viewBox="0 0 16 16"
            className="size-5 shrink-0 text-text-03"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
          >
            <path d="m3.5 8.5 3 3 6-6.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          className={`size-4 shrink-0 text-text-03 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {item?.state === "available" && (
          <ActionButton
            type="button"
            disabled={busy}
            aria-label={`Install ${item.name} quickly`}
            onClick={() =>
              run(async () => {
                await send("POST", `${CATALOG_URL}/${item.id}/install`, {});
                return `${item.name} installed${item.needs_account ? ". Open it to connect your account." : "."}`;
              })
            }
            className="flex size-9 shrink-0 items-center justify-center rounded-lg text-xl text-text-05 border border-border-02 disabled:opacity-50"
          >
            +
          </ActionButton>
        )}
      </ResponsiveLayout>
      {open && (
        <ResponsiveLayout className={`${card} mb-3 flex flex-col gap-4`}>
          {workspace && <WorkspaceAction source={workspace} status={workspaceStatus} busy={busy} run={run} />}
          {item && (
            <div className={workspace ? "border-t border-border-01 pt-4" : undefined}>
              <Card item={item} req={req} busy={busy} run={run} />
            </div>
          )}
        </ResponsiveLayout>
      )}
    </li>
  );
}

/**
 * Browse one entry per service. Each entry shows its workspace and personal actions.
 */
export default function IntegrationCatalog({
  initialIntegration,
  workspaceStatus,
  showExtraConnectors,
}: {
  initialIntegration?: string;
  workspaceStatus: WorkspaceStatus;
  showExtraConnectors?: boolean | null;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const connectorText = useWorkspaceTranslations("admin.addConnector");
  const connectorCatalog = useMemo(
    () => listSourceMetadata({ showExtraConnectors: showExtraConnectors ?? undefined }),
    [showExtraConnectors],
  );
  const catalog = useSWR<{ items: IntegrationItem[] }>(CATALOG_URL, errorHandlingFetcher);
  const requests = useSWR<{ my_requests: Req[]; workspace_sources: WorkspaceSource[] }>(
    REQUESTS_URL,
    errorHandlingFetcher,
    { refreshInterval: (data) => data?.workspace_sources.some((source) => source.my_request?.state === "pending") ? 10_000 : 0 },
  );
  const [category, setCategory] = useState("all");
  const [q, setQ] = useState(initialIntegration ?? "");
  const [openIds, setOpenIds] = useState<ReadonlySet<string>>(
    () => new Set(initialIntegration ? [initialIntegration] : []),
  );
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const run = (fn: () => Promise<string>) => {
    setBusy(true);
    setMsg(null);
    fn()
      .then(async (text) => {
        setMsg({ ok: true, text });
        await Promise.all([catalog.mutate(), requests.mutate()]);
      })
      .catch((e: unknown) =>
        setMsg({ ok: false, text: e instanceof Error ? e.message : "The request failed." }),
      )
      .finally(() => setBusy(false));
  };

  const reqFor = (id: string): Req | null =>
    (requests.data?.my_requests ?? []).find(
      (r) => r.item_key === `integration:${id}` && r.state !== "withdrawn",
    ) ?? null;

  const inShow = useMemo(() => {
    const entries = new Map<string, DirectoryEntry>();
    for (const item of catalog.data?.items ?? []) {
      entries.set(item.id, {
        id: item.id,
        name: item.name,
        description: item.description,
        category: item.category,
        integration: item,
      });
    }
    const workspaceSources = new Map(
      (requests.data?.workspace_sources ?? []).map((source) => [source.key, source]),
    );
    for (const metadata of connectorCatalog) {
      const key = metadata.internalName;
      const availability = workspaceSources.get(key);
      workspaceSources.set(key, {
        key,
        name: metadata.displayName,
        description: connectorText(SOURCE_DESCRIPTION_KEYS[key]),
        requestable: availability?.requestable ?? false,
        my_request: availability?.my_request,
        metadata,
      });
    }
    for (const key of workspaceStatus.configured) {
      if (!workspaceSources.has(key)) {
        const metadata = isValidSource(key) ? getSourceMetadata(key as ValidSources) : undefined;
        workspaceSources.set(key, {
          key,
          name: metadata?.displayName ?? titleCase(key),
          description: "Configured for company search.",
          requestable: false,
          metadata,
        });
      }
    }
    for (const workspace of workspaceSources.values()) {
      const metadata = workspace.metadata ?? (isValidSource(workspace.key)
        ? getSourceMetadata(workspace.key as ValidSources)
        : undefined);
      if (showExtraConnectors === false && metadata?.category === SourceCategory.AiObservability) continue;
      const id = integrationId(workspace.key);
      const entry = entries.get(id);
      const category = metadata?.category.toLowerCase() ?? entry?.category ?? "other";
      const source = { ...workspace, metadata };
      entries.set(
        id,
        entry
          ? { ...entry, category, workspace: source }
          : {
              id,
              name: workspace.name,
              description: workspace.description,
              category,
              workspace: source,
            },
      );
    }
    return [...entries.values()];
  }, [catalog.data, requests.data, workspaceStatus.configured, connectorCatalog, connectorText, showExtraConnectors]);
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    inShow.forEach((i) => counts.set(i.category, (counts.get(i.category) ?? 0) + 1));
    return [...counts.entries()].sort(([a], [b]) => categoryLabel(a).localeCompare(categoryLabel(b)));
  }, [inShow]);
  const visible = inShow.filter(
    (i) =>
      (category === "all" || i.category === category) &&
      (q.trim() === "" ||
        `${i.id} ${i.name} ${i.description} ${i.category}`.toLowerCase().includes(q.trim().toLowerCase())),
  );

  const sections = categories.map(([key]) => ({
    key,
    label: categoryLabel(key),
    items: visible.filter((entry) => entry.category === key).sort((a, b) => a.name.localeCompare(b.name)),
  })).filter((section) => section.items.length > 0);

  return (
    <section aria-label={workspaceText("catalog")} className="flex flex-col gap-4" data-testid="integration-catalog">
      <p className="text-sm text-text-03">{workspaceText("connectorCatalogCount", { count: connectorCatalog.length })}</p>
      <ResponsiveLayout display="flex" className="items-center gap-2">
        <label className="flex min-w-0 flex-1 flex-col text-sm font-medium text-text-05">
          <span className="sr-only">{workspaceText("search")}</span>
          <NativeInput
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={workspaceText("searchIntegrations")}
            className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05"
          />
        </label>
        <label
          className="flex flex-col text-sm font-medium text-text-05"
          data-testid="catalog-categories"
        >
          <span className="sr-only">{workspaceText("category")}</span>
          <NativeSelect
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05"
          >
            <option value="all">{workspaceText("all")}</option>
            {categories.map(([c, n]) => (
              <option key={c} value={c}>
                {categoryLabel(c)} ({n})
              </option>
            ))}
          </NativeSelect>
        </label>
      </ResponsiveLayout>
      <p
        role={msg?.ok === false ? "alert" : "status"}
        className={`min-h-5 text-sm ${msg?.ok === false ? "text-status-text-error-05" : "text-text-05"}`}
        data-testid="integration-message"
      >
        {msg?.text ?? ""}
      </p>
      {(catalog.isLoading || requests.isLoading) && <p className="text-sm text-text-03">{workspaceText("loadingTheCatalog")}</p>}
      {catalog.error && (
        <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("theCatalogCouldNotBeLoadedTryAgainIn")}</p>
      )}
      {requests.error && (
        <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("workspaceIntegrationOptionsCouldNotBeLoaded")}</p>
      )}
      {catalog.data && requests.data && visible.length === 0 && (
        <p className="text-sm text-text-03" data-testid="integration-empty">
          {inShow.length === 0
            ? "No integrations are available yet."
            : "Nothing matches. Try another search or category."}
        </p>
      )}
      {sections.map((sec) => (
        <ResponsiveLayout display="flex"
          key={sec.key}
          className="flex-col gap-2"
          data-testid={`section-${sec.label.toLowerCase()}`}
        >
          <h3 className="border-b border-border-01 pb-2 text-sm text-text-03">{sec.label}</h3>
          <ul className="grid gap-x-8 md:grid-cols-2">
            {sec.items.map((i) => (
              <Row
                key={i.id}
                entry={i}
                workspaceStatus={workspaceStatus}
                open={openIds.has(i.id)}
                onToggle={() => setOpenIds((previous) => {
                  const next = new Set(previous);
                  if (!next.delete(i.id)) next.add(i.id);
                  return next;
                })}
                req={reqFor(i.id)}
                busy={busy}
                run={run}
              />
            ))}
          </ul>
        </ResponsiveLayout>
      ))}
    </section>
  );
}
