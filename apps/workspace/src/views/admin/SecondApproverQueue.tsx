"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface QueueItem { id: string; target_name: string; owner_email: string; version: number; fingerprint: string; created_at: string }
interface Review { id: string; version: number; fingerprint: string; target_name: string; payload: { title: string; markdown: string } }

export const SECOND_QUEUE_URL = "/api/admin/actions/awaiting-second";
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const primary = "min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
const secondary = "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

async function post(url: string, body: unknown): Promise<void> {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  }
}

/**
 * Sends the owner approved that need a second person too. Opening one shows the exact content and is audited; the
 * server refuses it to the owner and to anyone who could not open every source it cites.
 */
export default function SecondApproverQueue() {
  const { data: queue, mutate } = useSWR<QueueItem[]>(SECOND_QUEUE_URL, errorHandlingFetcher, { refreshInterval: 30000 });
  const [review, setReview] = useState<Review | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
      await mutate();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "The request failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={card} aria-labelledby="second-q" data-testid="second-queue">
      <h2 id="second-q" className="text-base font-semibold text-text-05">Sends waiting for a second approver</h2>
      <p className="mt-1 text-sm text-text-03">
        Sends the owner has approved that need someone else to approve too. You do not see your own here. Opening one shows you the draft and is recorded in the audit log;
        you can only open it if you could open every source it cites.
      </p>
      {message && <p role="alert" className="mt-2 text-sm text-status-text-error-05">{message}</p>}
      {!queue || queue.length === 0 ? (
        <p className="mt-3 text-sm text-text-03">Nothing is waiting.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {queue.map((q) => (
            <li key={q.id} className="rounded-xl border border-border-01 px-3 py-3" data-testid="second-item">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="text-text-05">To <span className="font-medium">{q.target_name}</span> · from {q.owner_email} · {new Date(q.created_at).toLocaleString()}</span>
                <button
                  type="button"
                  className={secondary}
                  disabled={busy}
                  onClick={() => run(async () => {
                    const res = await fetch(`/api/admin/actions/${q.id}/second-review`, { method: "POST" });
                    const body = await res.json().catch(() => null);
                    if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `Could not open it (HTTP ${res.status}).`);
                    setReview(body as Review);
                  })}
                >
                  Open to review
                </button>
              </div>
              {review && review.id === q.id && (
                <div className="mt-3" data-testid="second-review">
                  <p className="text-xs text-text-03">The exact content that will be sent. Your approval covers this content and nothing else.</p>
                  <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-background-neutral-01 px-2 py-1 text-xs text-text-05">{review.payload.markdown}</pre>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={primary}
                      disabled={busy}
                      onClick={() => run(async () => { await post(`/api/admin/actions/${review.id}/second-approve`, { version: review.version, fingerprint: review.fingerprint }); setReview(null); })}
                    >
                      Approve this exact content
                    </button>
                    <button
                      type="button"
                      className={secondary}
                      disabled={busy}
                      onClick={() => run(async () => { await post(`/api/admin/actions/${review.id}/second-decline`, { version: review.version }); setReview(null); })}
                    >
                      Decline
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
