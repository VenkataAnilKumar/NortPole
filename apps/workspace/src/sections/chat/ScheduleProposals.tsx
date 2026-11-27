"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { NavLink } from "@opal/navigation";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

const URL = "/api/workflow-schedule-proposals";
const actionClass = "min-h-10 rounded-lg border border-border-02 px-3 text-sm font-medium disabled:opacity-50";

interface Proposal {
  id: string;
  operation: "create" | "run";
  state: "pending" | "queued" | "running" | "completed" | "failed" | "dismissed" | "expired" | "interrupted";
  preview: {
    name: string;
    request: string;
    desired_output: string;
    when: string;
    next_run_at: string | null;
    private_review: boolean;
    schedule_id: string | null;
  };
  result: { schedule_id: string | null; run_id: string | null; outcome: string | null; detail: string | null } | null;
}

const STATUS: Record<Proposal["state"], string> = {
  pending: "Awaiting confirmation",
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Could not complete",
  dismissed: "Dismissed",
  expired: "Expired",
  interrupted: "Result unavailable. Check Workflows before submitting again.",
};

const OUTCOME: Record<string, string> = {
  plan_ready: "Plan ready for approval",
  review_complete: "Review complete",
  needs_review: "Result needs review",
  no_new_csv: "No new file",
  drive_skipped: "Run skipped",
  skipped: "Run skipped",
  paused: "Schedule paused",
  plan_failed: "Could not prepare a plan",
};

function ScheduleProposalCard({
  proposal,
  onUpdate,
}: {
  proposal: Proposal;
  onUpdate: (updated: Proposal) => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { preview, result, operation, state } = proposal;
  const scheduleId = result?.schedule_id ?? preview.schedule_id;
  const status = result?.outcome ? OUTCOME[result.outcome] ?? STATUS[state] : STATUS[state];

  async function decide(decision: "confirm" | "dismiss") {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${URL}/${proposal.id}/${decision}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The request failed.");
      onUpdate(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label={workspaceText("scheduleProposal")} className="flex flex-col gap-3 rounded-xl border border-border-02 bg-background-neutral-00 p-4 text-text-05">
      <div>
        <h3 className="font-semibold">{operation === "create" ? "Create schedule" : "Run schedule now"}</h3>
        <p className="break-words text-sm font-medium">{preview.name}</p>
      </div>
      <div className="space-y-1 text-sm">
        <p>{preview.when}</p>
        {preview.next_run_at && (
          <p className="text-text-03">{operation === "create" ? "Expected first run" : "Next scheduled run"} · {new Date(preview.next_run_at).toLocaleString()}</p>
        )}
        <p className="whitespace-pre-wrap break-words">{preview.request}</p>
        {preview.desired_output && <p className="whitespace-pre-wrap break-words">{workspaceText("expectedOutput")}{" "}{preview.desired_output}</p>}
        <p className="text-text-03">{preview.private_review ? "The review saves a private result." : "The workflow prepares a plan for your approval."}</p>
      </div>
      <p role="status" className="text-sm text-text-03">{status}{result?.detail && ` · ${result.detail}`}</p>
      {error && <p role="alert" className="text-sm text-status-text-error-05">{error}</p>}
      <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
        {state === "pending" && (
          <>
            <ActionButton type="button" className={actionClass} disabled={busy} onClick={() => void decide("confirm")}>
              {operation === "create" ? "Confirm schedule" : "Confirm run"}
            </ActionButton>
            <ActionButton type="button" className={actionClass} disabled={busy} onClick={() => void decide("dismiss")}>{workspaceText("dismiss")}</ActionButton>
          </>
        )}
        {scheduleId && (
          <NavLink
            href={result?.run_id
              ? `/app/workflows/runs?run=${encodeURIComponent(result.run_id)}`
              : `/app/workflows/scheduled?schedule=${encodeURIComponent(scheduleId)}`}
            className="text-sm font-medium underline"
          >
            {result?.run_id ? "Open run" : "Open schedule"}
          </NavLink>
        )}
      </ResponsiveLayout>
    </section>
  );
}

export default function ScheduleProposals({ chatId, streaming, className }: { chatId: string; streaming: boolean; className: string }) {
  const { data, mutate } = useSWR<Proposal[]>(`${URL}?chat_id=${encodeURIComponent(chatId)}`, errorHandlingFetcher, {
    refreshInterval: (rows) => rows?.some(({ state }) => state === "queued" || state === "running") ? 2000 : 0,
    shouldRetryOnError: false,
  });
  useEffect(() => {
    if (!streaming) void mutate();
  }, [streaming, mutate]);

  const current = data?.filter(({ state }) => state !== "dismissed" && state !== "expired");
  if (!current?.length) return null;
  return (
    <div className={className}>
      <ResponsiveLayout display="flex" className="flex-col gap-3">
        {current.map((proposal) => (
          <ScheduleProposalCard
            key={proposal.id}
            proposal={proposal}
            onUpdate={(updated) => void mutate(
              (rows) => rows?.map((row) => row.id === updated.id ? updated : row),
              { revalidate: false },
            )}
          />
        ))}
      </ResponsiveLayout>
    </div>
  );
}
