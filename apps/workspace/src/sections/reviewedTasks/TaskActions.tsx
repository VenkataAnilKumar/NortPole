"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface Action {
  id: string;
  target_name: string;
  state: "proposed" | "awaiting_second" | "approved" | "executing" | "succeeded" | "failed" | "cancelled";
  version: number;
  fingerprint: string;
  payload: { title: string; markdown: string };
  attempts: number;
  result_status: number | null;
  error: string | null;
  executed_at: string | null;
  needs_second_approval?: boolean;
}
interface Target {
  tier?: string;
  needs_second_approval?: boolean;
  id: number;
  name: string;
}

const STATE_LABEL: Record<Action["state"], string> = {
  proposed: "Waiting for your approval",
  awaiting_second: "Waiting for a second person to approve",
  approved: "Approved, ready to send",
  executing: "Sending",
  succeeded: "Sent",
  failed: "Send failed",
  cancelled: "Cancelled",
};

const card = "rounded-xl border border-border-01 px-3 py-3";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

async function post(path: string, body: unknown): Promise<void> {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `The request failed (HTTP ${res.status}).`);
  }
}

/**
 * Send an approved draft to a destination an administrator registered. The
 * content that will be sent is shown in full and the approval covers exactly
 * that content; the server checks policy and your access again when sending.
 */
export default function TaskActions({ taskId }: { taskId: string }) {
  const { data: targets } = useSWR<Target[]>("/api/action-targets", errorHandlingFetcher);
  const { data: actions, mutate } = useSWR<Action[]>(`/api/tasks/${taskId}/actions`, errorHandlingFetcher);
  const [targetId, setTargetId] = useState<number | "">("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The request failed.");
    } finally {
      await mutate();
      setBusy(null);
    }
  };

  const list = actions ?? [];
  const noTargets = targets !== undefined && targets.length === 0;

  return (
    <section className="mt-5 border-t border-border-01 pt-4" aria-labelledby="send-h" data-testid="task-actions">
      <h3 id="send-h" className="mb-2 text-sm font-semibold text-text-05">Send this draft</h3>
      {noTargets ? (
        <p className="text-sm text-text-03">No destination is set up yet. An administrator registers where drafts may be sent.</p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-text-05">
            Destination
            <select
              className="min-h-11 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">Choose a destination…</option>
              {(targets ?? []).map((t) => (
                <option key={t.id} value={t.id} disabled={t.tier === "read_only"}>{t.name}{t.tier === "draft_only" ? " (draft only: cannot be sent)" : t.tier === "read_only" ? " (read only)" : t.needs_second_approval ? " (needs a second person to approve)" : ""}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={secondary}
            disabled={!!busy || targetId === ""}
            onClick={() => run("propose", () => post(`/api/tasks/${taskId}/actions`, { target_id: targetId }))}
          >
            {busy === "propose" ? "Preparing…" : "Review what will be sent"}
          </button>
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-sm text-status-text-error-05">{error}</p>}

      {list.length > 0 && (
        <ul className="mt-3 flex flex-col gap-3" data-testid="action-list">
          {list.map((a) => {
            const open = a.state === "proposed" || a.state === "awaiting_second" || a.state === "approved" || a.state === "failed";
            return (
              <li key={a.id} className={card} data-testid="action-item">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="font-medium text-text-05">To {a.target_name}</span>
                  <span data-testid="action-state" className="rounded-full border border-border-01 px-2.5 py-0.5 text-xs text-text-03">
                    {STATE_LABEL[a.state]}
                  </span>
                </div>
                {open && (
                  <details open={a.state === "proposed"} className="mt-2 text-xs text-text-03">
                    <summary className="cursor-pointer">The exact content that will be sent</summary>
                    <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1 text-text-05">{a.payload.markdown}</pre>
                  </details>
                )}
                {a.state === "awaiting_second" && (
                  <p className="mt-2 text-xs text-text-03" data-testid="awaiting-second">
                    You approved this content. {a.target_name} also needs a second person, who is not you, to approve the same content before it can be sent. Nothing has been sent.
                  </p>
                )}
                {a.error && <p role="alert" className="mt-2 text-xs text-status-text-error-05">{a.error}</p>}
                {a.state === "succeeded" && (
                  <p className="mt-2 text-xs text-text-03">
                    Delivered{a.executed_at ? ` on ${new Date(a.executed_at).toLocaleString()}` : ""} (status {a.result_status}).
                  </p>
                )}
                {a.attempts > 1 && <p className="mt-1 text-xs text-text-03">Attempts: {a.attempts}. A retry reuses the same request key, so it is not sent twice.</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  {a.state === "proposed" && (
                    <button
                      type="button"
                      className={primary}
                      disabled={!!busy}
                      onClick={() => run(`approve-${a.id}`, () => post(`/api/actions/${a.id}/approve`, { version: a.version, fingerprint: a.fingerprint }))}
                    >
                      {a.needs_second_approval ? "Approve (a second person must also approve)" : "Approve this exact content"}
                    </button>
                  )}
                  {(a.state === "approved" || a.state === "failed") && (
                    <button type="button" className={primary} disabled={!!busy} onClick={() => run(`send-${a.id}`, () => post(`/api/actions/${a.id}/execute`, { version: a.version }))}>
                      {busy === `send-${a.id}` ? "Sending…" : a.state === "failed" ? "Try again" : "Send"}
                    </button>
                  )}
                  {open && (
                    <button type="button" className={secondary} disabled={!!busy} onClick={() => run(`cancel-${a.id}`, () => post(`/api/actions/${a.id}/cancel`, { version: a.version }))}>
                      Cancel
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
