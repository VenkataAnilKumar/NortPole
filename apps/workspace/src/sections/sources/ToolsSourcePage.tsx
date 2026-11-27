"use client";

import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { Button, NativeTextArea } from "@opal/components";
import { ResponsiveLayout } from "@opal/layouts";
import { NavLink } from "@opal/navigation";
import { type FormEvent, useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { useSettings } from "@/lib/settings/hooks";
import { card, h1Class, pageClass } from "@/sections/sources/shared";
import { REQUESTS_URL, send } from "@/sections/sources/integrations";

interface Kind {
  kind: string;
  label: string;
  on: boolean;
}
interface Tool {
  name: string;
  kind_label: string;
  allowed: boolean;
  mine: boolean;
  workspace_request_key: string | null;
}

interface DiscoverItem {
  kind: string;
  key: string;
  my_request: { state: string; decision_note: string } | null;
}

function requestIsOpen(state: string | undefined) {
  return state === "pending" || state === "approved";
}

export default function ToolsSourcePage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [asking, setAsking] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const { data, error, isLoading, mutate: refreshTools } = useSWR<{ kinds: Kind[]; tools: Tool[] }>(
    "/api/tool-catalog",
    errorHandlingFetcher,
  );
  const requests = useSWR<{ items: DiscoverItem[] }>(
    data?.tools.some((tool) => tool.workspace_request_key) ? REQUESTS_URL : null,
    errorHandlingFetcher,
    {
      refreshInterval: (latest) => latest?.items.some(
        (item) => item.kind === "plugin" && requestIsOpen(item.my_request?.state),
      ) ? 10_000 : 0,
      onSuccess: (latest) => {
        const keys = new Set(latest.items.filter((item) => item.kind === "plugin").map((item) => item.key));
        if (data?.tools.some((tool) => tool.workspace_request_key && !keys.has(tool.workspace_request_key))) {
          void refreshTools().catch(() => undefined);
        }
      },
    },
  );
  const requestItems = new Map(
    requests.data?.items.filter((item) => item.kind === "plugin").map((item) => [item.key, item]),
  );
  const craft = useSettings().nortpole_craft_enabled === true;
  const tools = [...(data?.tools ?? [])].sort(
    (a, b) => Number(b.allowed) - Number(a.allowed) || a.name.localeCompare(b.name),
  );

  async function requestTool(event: FormEvent<HTMLFormElement>, itemKey: string) {
    event.preventDefault();
    if (busy) return;
    const reason = new FormData(event.currentTarget).get("reason");
    setBusy(true);
    setMessage(null);
    try {
      await send("POST", "/api/sources/requests", {
        kind: "plugin",
        item_key: itemKey,
        reason: typeof reason === "string" ? reason : "",
      });
      setAsking(null);
      setMessage({ ok: true, text: workspaceText("workspaceRequest.sent") });
    } catch (error) {
      setMessage({
        ok: false,
        text: error instanceof Error ? error.message : "The request failed.",
      });
    } finally {
      await requests.mutate().catch(() => undefined);
      setBusy(false);
    }
  }

  return (
    <div className={pageClass} data-testid="tools-source-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>{workspaceText("tools")}</h1>
        <p className="text-sm text-text-03">{workspaceText("toolsAssistantsMayUseAToolThatIsNot")}</p>
        {craft && (
          <p className="text-sm text-text-03">
            <NavLink href="/app/plugins" className="font-semibold text-text-05 underline">{workspaceText("manageYourOwnTools")}</NavLink>
          </p>
        )}
      </header>
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loadingTools")}</p>}
      {error && (
        <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("toolsCouldNotBeLoadedTryAgainInA")}</p>
      )}
      {data && (
        <>
          <section className={card} aria-labelledby="pl-kinds">
            <h2 id="pl-kinds" className="text-base font-semibold text-text-05">{workspaceText("kindsOfTool")}</h2>
            <ul className="mt-2 flex flex-col gap-1">
              {data.kinds.map((k) => (
                <li
                  key={k.kind}
                  className="flex flex-wrap justify-between gap-2 text-sm"
                  data-testid="pl-kind"
                >
                  <span className="text-text-05">{k.label}</span>
                  <span className={k.on ? "text-text-05" : "text-text-03"}>
                    {k.on ? "Allowed" : "Not allowed"}
                  </span>
                </li>
              ))}
            </ul>
          </section>
          <section className={card} aria-labelledby="pl-tools">
            <h2 id="pl-tools" className="text-base font-semibold text-text-05">{workspaceText("tools")}</h2>
            {message && (
              <p role={message.ok ? "status" : "alert"} className={message.ok ? "mt-2 text-sm text-text-05" : "mt-2 text-sm text-status-text-error-05"}>
                {message.text}
              </p>
            )}
            {requests.error && (
              <p role="alert" className="mt-2 text-sm text-status-text-error-05">
                {workspaceText("discoverCouldNotBeLoadedTryAgainInA")}
              </p>
            )}
            {tools.length === 0 ? (
              <p className="mt-1 text-sm text-text-03">{workspaceText("noToolsAreSetUp")}</p>
            ) : (
              <ul className="mt-2 flex flex-col divide-y divide-border-01">
                {tools.map((t, i) => {
                  const item = t.workspace_request_key ? requestItems.get(t.workspace_request_key) : undefined;
                  const state = item?.my_request?.state;
                  const canRequest = item && !requestIsOpen(state);
                  const requestStatus = state === "approved" ? "awaitingSetupStatus"
                    : state === "pending" || state === "declined" ? state : null;
                  return (
                    <li
                      key={t.workspace_request_key ? `request-${t.workspace_request_key}` : `${t.name}-${i}`}
                      className="flex flex-wrap items-baseline justify-between gap-2 py-2 text-sm"
                      data-testid="pl-tool"
                    >
                      <span className="min-w-0">
                        <span className="font-medium text-text-05">{t.name}</span>
                        <span className="block text-xs text-text-03">
                          {t.kind_label}
                          {t.mine ? " · added by you" : ""}
                        </span>
                      </span>
                      <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
                        <span className={t.allowed ? "text-text-05" : "text-text-03"}>
                          {t.allowed ? "Allowed" : "Not allowed"}
                        </span>
                        {requestStatus && (
                          <span className="rounded-full border border-border-02 px-2.5 py-0.5 text-xs text-text-04">
                            {workspaceText(`workspaceRequest.${requestStatus}`)}
                          </span>
                        )}
                        {canRequest && asking !== item.key && (
                          <Button
                            type="button"
                            size="sm"
                            prominence="secondary"
                            disabled={busy}
                            aria-label={`${workspaceText("request")} ${t.name}`}
                            onClick={() => { setAsking(item.key); setMessage(null); }}
                          >
                            {workspaceText(state === "declined" ? "workspaceRequest.again" : "request")}
                          </Button>
                        )}
                      </ResponsiveLayout>
                      {item?.my_request?.decision_note && (
                        <p className="w-full whitespace-pre-wrap wrap-anywhere text-xs text-text-03">
                          {workspaceText("administratorSNote")} {item.my_request.decision_note}
                        </p>
                      )}
                      {canRequest && asking === item.key && (
                        <form className="w-full space-y-2" onSubmit={(event) => void requestTool(event, item.key)}>
                          <label className="block space-y-1 text-sm text-text-04">
                            <span>{workspaceText("whyWouldItHelpOptional")}</span>
                            <NativeTextArea
                              name="reason"
                              maxLength={500}
                              className="block min-h-20 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 py-2"
                            />
                          </label>
                          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                            <Button type="submit" disabled={busy}>{workspaceText("sendRequest")}</Button>
                            <Button type="button" prominence="secondary" disabled={busy} onClick={() => setAsking(null)}>
                              {workspaceText("cancel")}
                            </Button>
                          </ResponsiveLayout>
                        </form>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
