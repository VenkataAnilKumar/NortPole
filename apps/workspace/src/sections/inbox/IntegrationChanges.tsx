"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";

export const PROPOSALS_URL = "/api/integration-proposals";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 shadow-sm";
const button = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
const primary = "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";

export interface Proposal {
  id: string;
  integration_id: string;
  integration_name: string;
  summary: string;
  arguments: Record<string, unknown>;
  state: string;
  outcome: string | null;
  created_at: string;
  expires_at: string;
}

/** Share the pending feed across the Inbox and sidebar badge. */
export function usePendingProposals() {
  const { data, mutate } = useSWR<{ items: Proposal[] }>(
    SWR_KEYS.inboxPendingProposals,
    errorHandlingFetcher,
    { refreshInterval: 15_000, shouldRetryOnError: false }
  );
  return { waiting: (data?.items ?? []).filter((p) => p.state === "pending"), mutate };
}

const FAILURE: Record<string, string> = {
  blocked: "your administrator has blocked it since",
  not_connected: "the account is no longer connected",
  not_installed: "it is no longer installed",
  changed: "the integration was updated since",
  service_error: "the service refused it",
};

/**
 * Changes an assistant proposed in chat. Nothing has been sent: each one shows the exact arguments that will go if you
 * approve, runs once, and is checked again against your administrator's policy at that moment.
 */
export default function IntegrationChanges() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { waiting, mutate } = usePendingProposals();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  if (waiting.length === 0 && !msg) return null;

  const decide = async (p: Proposal, verb: "approve" | "decline") => {
    setBusy(p.id);
    setMsg(null);
    try {
      const res = await fetch(`${PROPOSALS_URL}/${p.id}/${verb}`, { method: "POST" });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "The decision could not be saved.");
      if (verb === "decline") setMsg({ ok: true, text: `Declined: ${p.summary}. Nothing was sent.` });
      else if (body.state === "executed") setMsg({ ok: true, text: `Done: ${p.summary}.` });
      else setMsg({ ok: false, text: `It was not done: ${FAILURE[body.outcome ?? ""] ?? "it could not be completed"}.` });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "The decision could not be saved." });
    } finally {
      setBusy(null);
      await mutate();
    }
  };

  return (
    <section className="flex flex-col gap-3" aria-labelledby="inbox-changes" data-testid="integration-changes">
      <h2 id="inbox-changes" className="text-base font-semibold text-text-05">{workspaceText("changesWaitingForYourYes")}</h2>
      <p className="text-sm text-text-03">{workspaceText("proposedByAnAssistantInChatNothingIsSent")}</p>
      <p role={msg?.ok === false ? "alert" : "status"} className={`min-h-5 text-sm ${msg?.ok === false ? "text-status-text-error-05" : "text-text-05"}`}>{msg?.text ?? ""}</p>
      <ul className={`${card} overflow-hidden`} aria-label={workspaceText("changesWaitingForYourYes")}>
        {waiting.map((p) => (
          <li key={p.id} className="flex flex-col gap-2 border-t border-border-01 px-5 py-4 first:border-t-0" data-testid="integration-change">
            <div className="text-sm font-semibold text-text-05">{p.summary}</div>
            <div className="text-xs text-text-03">{p.integration_name}{" "}{workspaceText("proposedInChat")}</div>
            <div className="text-xs text-text-03">{workspaceText("proposed")}{" "}{new Date(p.created_at).toLocaleString()}{" "}{workspaceText("expires")}{" "}{new Date(p.expires_at).toLocaleString()}</div>
            <pre className="max-h-48 overflow-auto rounded-xl bg-background-neutral-02 p-3 text-xs text-text-05" aria-label={`What will be sent for ${p.summary}`}>{JSON.stringify(p.arguments, null, 2)}</pre>
            <ResponsiveLayout display="flex" className="flex-wrap gap-2">
              <ActionButton type="button" className={primary} disabled={busy !== null} aria-label={`Approve: ${p.summary}`} onClick={() => void decide(p, "approve")}>{busy === p.id ? "Working…" : "Approve and send"}</ActionButton>
              <ActionButton type="button" className={button} disabled={busy !== null} aria-label={`Decline: ${p.summary}`} onClick={() => void decide(p, "decline")}>{workspaceText("decline")}</ActionButton>
            </ResponsiveLayout>
          </li>
        ))}
      </ul>
    </section>
  );
}
