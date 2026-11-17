"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { dismissNotification, invalidateNotificationCaches } from "@/lib/notifications/api";
import { type Notification } from "@/lib/notifications/interfaces";
import { isAction } from "@/lib/notifications/inbox";
import { useOwnWork, type OwnTask } from "@/lib/inboxWork";
import { SvgEmpty } from "@opal/illustrations";
import { useApprovalCounts } from "@/lib/approvals";
import { useUser } from "@/providers/UserProvider";
import LiveApprovals from "@/sections/inbox/LiveApprovals";
import IntegrationChanges, { usePendingProposals } from "@/sections/inbox/IntegrationChanges";

type Tab = "approve" | "review" | "updates";

const TABS: { id: Tab; label: string }[] = [
  { id: "approve", label: "To approve" },
  { id: "review", label: "To review" },
  { id: "updates", label: "Updates" },
];

const EMPTY: Record<Tab, { title: string; body: string }> = {
  approve: {
    title: "Nothing to approve",
    body: "Plans waiting for your yes and approvals you are asked to give appear here, each tied to one exact version or action.",
  },
  review: {
    title: "Nothing to review",
    body: "Drafts that are ready for you to check appear here.",
  },
  updates: {
    title: "No updates",
    body: "Finished and failed runs, decisions on your requests and announcements from your administrator appear here.",
  },
};

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 shadow-sm";
const button = "inline-flex min-h-10 items-center rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

function TaskRow({ t, label, action }: { t: OwnTask; label: string; action: string }) {
  return (
    <li className="flex flex-wrap items-center gap-3 border-t border-border-01 px-5 py-4 first:border-t-0" data-testid="inbox-task">
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-text-05">{t.title || "Untitled draft"}</div>
        <div className="mt-0.5 text-sm text-text-03">{label}</div>
        <div className="mt-1 text-xs text-text-03">{new Date(t.updated_at).toLocaleString()}</div>
      </div>
      <a href={`/app/workflows/drafts?task=${encodeURIComponent(t.id)}`} className={button}>{action}</a>
    </li>
  );
}

/**
 * Inbox: what waits for this person, in three fixed filters. To approve: plans to accept and approvals asked of them
 * (and, for administrators, a pointer to admin Approvals). To review: drafts ready to check. Updates: everything else.
 */
export default function InboxPage() {
  const [tab, setTab] = useState<Tab>("approve");
  const [showDismissed, setShowDismissed] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const { data, error, isLoading, mutate } = useSWR<{ notifications: Notification[] }>(SWR_KEYS.notificationsPage(0, 50), errorHandlingFetcher);
  const { data: live } = useSWR<{ items: unknown[] }>(SWR_KEYS.myLiveApprovals, errorHandlingFetcher, { refreshInterval: 15_000, shouldRetryOnError: false });
  const own = useOwnWork(30_000);
  const proposalCount = (usePendingProposals().data?.items ?? []).filter((p) => p.state === "pending").length;
  const { isAdmin } = useUser();
  const all = data?.notifications ?? [];
  const liveCount = live?.items.length ?? 0;
  const open = all.filter((n) => !n.dismissed);
  const actionNotes = open.filter(isAction);
  const updates = open.filter((n) => !isAction(n));
  const dismissed = all.filter((n) => n.dismissed);
  const counts: Record<Tab, number> = {
    approve: own.plans.length + actionNotes.length + liveCount + proposalCount,
    review: own.drafts.length,
    updates: updates.length,
  };

  const dismiss = async (id: number) => {
    setBusyId(id);
    try {
      await dismissNotification(id);
      await invalidateNotificationCaches();
      await mutate();
    } finally {
      setBusyId(null);
    }
  };

  const notes = (list: Notification[]) => (
    <ul className={`${card} overflow-hidden`}>
      {list.map((n) => (
        <li key={n.id} className="flex flex-wrap items-center gap-3 border-t border-border-01 px-5 py-4 first:border-t-0" data-testid="inbox-note">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-text-05">{n.title}</div>
            {n.description && <div className="mt-0.5 text-sm text-text-03">{n.description}</div>}
            <div className="mt-1 text-xs text-text-03">{new Date(n.first_shown).toLocaleString()}</div>
          </div>
          {!n.dismissed && (
            <button type="button" onClick={() => dismiss(n.id)} disabled={busyId === n.id} className={button}>
              {busyId === n.id ? "Working…" : "Dismiss"}
            </button>
          )}
        </li>
      ))}
    </ul>
  );

  const empty = (t: Tab) => (
    <section className={`${card} flex flex-col items-center p-8 text-center`} aria-labelledby="inbox-empty">
      <SvgEmpty size={96} aria-hidden="true" />
      <h2 id="inbox-empty" className="mb-1 text-base font-semibold text-text-05">{EMPTY[t].title}</h2>
      <p className="text-sm text-text-03">{EMPTY[t].body}</p>
    </section>
  );

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-8" data-testid="inbox-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Inbox</h1>
        <p className="text-sm text-text-03">What is waiting for you. Open an item to see the exact version or action.</p>
      </header>

      <div role="tablist" aria-label="Inbox filter" className="flex gap-1 overflow-x-auto border-b border-border-01">
        {TABS.map((t) => (
          <button
            key={t.id}
            id={`inbox-tab-${t.id}`}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            aria-controls="inbox-panel"
            onClick={() => setTab(t.id)}
            className={`min-h-11 shrink-0 px-2.5 text-sm sm:px-4 font-semibold ${tab === t.id ? "border-b-2 border-text-05 text-text-05" : "text-text-03 hover:text-text-05"}`}
            data-testid={`inbox-tab-${t.id}`}
          >
            {t.label}
            {counts[t.id] > 0 && <>{" "}<span className="ml-1 rounded-full bg-background-neutral-02 px-2 py-0.5 text-xs">{counts[t.id]}<span className="sr-only"> waiting</span></span></>}
          </button>
        ))}
      </div>

      <div id="inbox-panel" role="tabpanel" aria-labelledby={`inbox-tab-${tab}`} className="flex flex-col gap-4">
        {isLoading ? (
          <p className="text-sm text-text-03">Loading…</p>
        ) : error ? (
          <div className={`${card} p-5`} role="alert"><p className="text-sm text-text-05">The inbox could not be loaded. Try again in a moment.</p></div>
        ) : tab === "approve" ? (
          <>
            {isAdmin && <AdminWaiting />}
            <LiveApprovals />
            <IntegrationChanges />
            {own.plans.length > 0 && (
              <ul className={`${card} overflow-hidden`} aria-label="Plans to accept">
                {own.plans.map((t) => <TaskRow key={t.id} t={t} label={t.schedule_name ? `Scheduled: ${t.schedule_name}. Plan ready: accept it to start the work` : "Plan ready: accept it to start the work"} action="Review the plan" />)}
              </ul>
            )}
            {actionNotes.length > 0 && notes(actionNotes)}
            {counts.approve === 0 && empty("approve")}
          </>
        ) : tab === "review" ? (
          own.drafts.length > 0 ? (
            <ul className={`${card} overflow-hidden`} aria-label="Drafts to review">
              {own.drafts.map((t) => <TaskRow key={t.id} t={t} label="Draft ready to review" action="Review the draft" />)}
            </ul>
          ) : empty("review")
        ) : (
          <>
            {updates.length > 0 ? notes(updates) : empty("updates")}
            {dismissed.length > 0 && (
              <div>
                <button type="button" className={button} aria-expanded={showDismissed} onClick={() => setShowDismissed(!showDismissed)}>
                  {showDismissed ? "Hide dismissed" : `Show dismissed (${dismissed.length})`}
                </button>
                {showDismissed && <div className="mt-3">{notes(dismissed)}</div>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** For administrators: what waits in admin Approvals, as one line with a link. Not counted in the Inbox numbers. */
function AdminWaiting() {
  const c = useApprovalCounts();
  if (!c.loaded || c.total === 0) return null;
  return (
    <section className={`${card} flex flex-wrap items-center justify-between gap-3 p-5`} aria-labelledby="inbox-admin" data-testid="inbox-admin-waiting">
      <div className="min-w-0">
        <h2 id="inbox-admin" className="text-sm font-semibold text-text-05">As an administrator</h2>
        <p className="text-sm text-text-03">{c.total} {c.total === 1 ? "item waits" : "items wait"} in Approvals.</p>
      </div>
      <a href="/admin/approvals" className={button}>Open Approvals</a>
    </section>
  );
}
