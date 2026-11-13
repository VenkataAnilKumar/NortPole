"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { postApprovalDecision } from "@/app/craft/services/apiServices";
import PayloadView from "@/app/craft/components/approvals/PayloadView";
import type { ApprovalListResponse } from "@/app/craft/types/approvals";

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 shadow-sm";

/**
 * Requests from the person's own tasks that are waiting for a decision. Each
 * decision covers this one action only: the session-wide choice is not offered
 * here, whatever the server allows elsewhere.
 */
export default function LiveApprovals() {
  const { data, mutate } = useSWR<ApprovalListResponse>(SWR_KEYS.myLiveApprovals, errorHandlingFetcher, {
    refreshInterval: 15_000,
    shouldRetryOnError: false,
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const items = data?.items ?? [];
  if (items.length === 0) return null;

  const decide = async (id: string, decision: "approve_once" | "reject") => {
    setBusy(id);
    setFailed(null);
    try {
      await postApprovalDecision(id, decision);
      await mutate();
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "The decision could not be saved.");
      await mutate();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-labelledby="live-approvals" data-testid="live-approvals" className="flex flex-col gap-3">
      <h2 id="live-approvals" className="text-sm font-semibold text-text-05">
        Waiting for your decision
      </h2>
      {failed && (
        <p role="alert" className="text-sm text-status-text-error-05">{failed}</p>
      )}
      {items.map((a) => {
        const first = a.actions[0];
        return (
          <article key={a.approval_id} className={`${card} p-5`}>
            <div className="mb-1 text-sm font-semibold text-text-05">
              {first?.display_name ?? "Action"} on {a.app_name}
            </div>
            {first?.description && <p className="mb-3 text-sm text-text-03">{first.description}</p>}
            <PayloadView payload={a.display_payload} />
            <p className="mt-3 text-xs text-text-03">
              Your decision covers this one action with exactly the content shown above. A different action asks again.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy === a.approval_id}
                onClick={() => decide(a.approval_id, "approve_once")}
                className="min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50"
              >
                {busy === a.approval_id ? "Working…" : "Approve this action"}
              </button>
              <button
                type="button"
                disabled={busy === a.approval_id}
                onClick={() => decide(a.approval_id, "reject")}
                className="min-h-11 rounded-xl border border-border-02 px-5 text-sm font-semibold text-text-05 disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </article>
        );
      })}
    </section>
  );
}
