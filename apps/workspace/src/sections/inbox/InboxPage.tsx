"use client";

import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { dismissNotification, invalidateNotificationCaches } from "@/lib/notifications/api";
import { NotificationType, type Notification } from "@/lib/notifications/interfaces";

type Tab = "action" | "resolved" | "updates";

interface Feed {
  notifications: Notification[];
}

/** Notification types that ask the reader to decide something. */
const ACTION_TYPES = new Set<NotificationType>([
  NotificationType.APPROVAL_REQUESTED,
  NotificationType.SCHEDULED_TASK_AWAITING_APPROVAL,
  NotificationType.SCHEDULED_TASK_PRE_APPROVED_ACTION,
]);

const TABS: { id: Tab; label: string }[] = [
  { id: "action", label: "Needs action" },
  { id: "resolved", label: "Resolved" },
  { id: "updates", label: "Updates" },
];

const EMPTY: Record<Tab, { title: string; body: string }> = {
  action: {
    title: "Nothing needs your attention",
    body: "Approvals you are asked to give appear here, each tied to one exact version or action. Notifications never include source or report text.",
  },
  resolved: {
    title: "Nothing resolved yet",
    body: "Items you have approved, rejected or dismissed are listed here.",
  },
  updates: {
    title: "No updates",
    body: "Run completions, failures and announcements from your administrator appear here.",
  },
};

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 shadow-sm";

export default function InboxPage() {
  const [tab, setTab] = useState<Tab>("action");
  const [busyId, setBusyId] = useState<number | null>(null);
  const { data, error, isLoading, mutate } = useSWR<Feed>(
    SWR_KEYS.notificationsPage(0, 50),
    errorHandlingFetcher
  );
  const all = data?.notifications ?? [];

  const byTab: Record<Tab, Notification[]> = {
    action: all.filter((n) => !n.dismissed && ACTION_TYPES.has(n.notif_type)),
    updates: all.filter((n) => !n.dismissed && !ACTION_TYPES.has(n.notif_type)),
    resolved: all.filter((n) => n.dismissed),
  };
  const items = byTab[tab];

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

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-8" data-testid="inbox-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Inbox</h1>
        <p className="text-sm text-text-03">Approvals and run updates. Open an item to review the exact version or action.</p>
      </header>

      <div role="tablist" aria-label="Inbox filter" className="flex gap-1 border-b border-border-01">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`min-h-11 px-4 text-sm font-semibold ${tab === t.id ? "border-b-2 border-text-05 text-text-05" : "text-text-03 hover:text-text-05"}`}
          >
            {t.label}
            {byTab[t.id].length > 0 && (
              <span className="ml-2 rounded-full bg-background-neutral-02 px-2 py-0.5 text-xs">{byTab[t.id].length}</span>
            )}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-text-03">Loading…</p>
      ) : error ? (
        <div className={`${card} p-5`} role="alert">
          <p className="text-sm text-text-05">The inbox could not be loaded. Try again in a moment.</p>
        </div>
      ) : items.length === 0 ? (
        <section className={`${card} p-5`} aria-labelledby="inbox-empty">
          <h2 id="inbox-empty" className="mb-1 text-base font-semibold text-text-05">{EMPTY[tab].title}</h2>
          <p className="text-sm text-text-03">{EMPTY[tab].body}</p>
        </section>
      ) : (
        <ul className={`${card} overflow-hidden`}>
          {items.map((n) => (
            <li key={n.id} className="flex flex-wrap items-center gap-3 border-t border-border-01 px-5 py-4 first:border-t-0">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-text-05">{n.title}</div>
                {n.description && <div className="mt-0.5 text-sm text-text-03">{n.description}</div>}
                <div className="mt-1 text-xs text-text-03">{new Date(n.first_shown).toLocaleString()}</div>
              </div>
              {!n.dismissed && (
                <button
                  type="button"
                  onClick={() => dismiss(n.id)}
                  disabled={busyId === n.id}
                  className="min-h-10 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50"
                >
                  {busyId === n.id ? "Working…" : "Dismiss"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
