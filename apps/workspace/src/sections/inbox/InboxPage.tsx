"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton } from "@opal/components";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import { useSettings } from "@/lib/settings/hooks";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { dismissNotification, invalidateNotificationCaches } from "@/lib/notifications/api";
import type { InboxNotificationSummary, InboxTab, NotificationsResponse } from "@/lib/notifications/interfaces";
import { inboxNotificationContext, inboxNotificationLink } from "@/lib/notifications/inbox";
import { useOwnWork, type OwnTask } from "@/lib/inboxWork";
import { SvgEmpty } from "@opal/illustrations";
import { useApprovalCounts } from "@/lib/approvals";
import { useUser } from "@/providers/UserProvider";
import LiveApprovals from "@/sections/inbox/LiveApprovals";
import IntegrationChanges, { usePendingProposals } from "@/sections/inbox/IntegrationChanges";

type Tab = Exclude<InboxTab, "dismissed" | "history">;

const PAGE_SIZE = 25;

const NOTIFICATION_LABEL: Record<InboxTab, string> = {
  approve: "Approval notifications",
  review: "Review notifications",
  updates: "Inbox updates",
  dismissed: "Dismissed notifications",
  history: "Workflow history",
};

const TABS: { id: Tab; label: string }[] = [
  { id: "approve", label: "To approve" },
  { id: "review", label: "To review" },
  { id: "updates", label: "Updates" },
];

const EMPTY: Record<Tab, { title: string; body: string }> = {
  approve: {
    title: "Nothing to approve",
    body: "Plans waiting for your yes and approvals you are asked to give appear here, each tied to a specific version or action.",
  },
  review: {
    title: "Nothing to review",
    body: "Drafts and workflow results that need your review appear here.",
  },
  updates: {
    title: "No updates",
    body: "Finished and failed runs, decisions on your requests and announcements from your administrator appear here.",
  },
};

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 shadow-sm";
const button = "inline-flex min-h-10 items-center rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";

function TaskRow({ t, label, action }: { t: OwnTask; label: string; action: string }) {
  const source = t.schedule_name ? `Scheduled workflow · ${t.schedule_name}` : "Drafts";
  return (
    <li className="flex flex-wrap items-center gap-3 border-t border-border-01 px-5 py-4 first:border-t-0" data-testid="inbox-task">
      <div className="min-w-0 flex-1 break-words">
        <div className="mb-1 text-xs text-text-03">{source}</div>
        <div className="text-sm font-semibold text-text-05">{t.title || "Untitled draft"}</div>
        <div className="mt-0.5 text-sm text-text-03">{label}</div>
        <div className="mt-1 text-xs text-text-03">{new Date(t.updated_at).toLocaleString()}</div>
      </div>
      <NavLink href={`/app/workflows/drafts?task=${encodeURIComponent(t.id)}`} className={button}>{action}</NavLink>
    </li>
  );
}

function NotificationList({ tab, total, empty }: {
  tab: InboxTab;
  total?: number;
  empty?: ReactNode;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [selectedPage, setSelectedPage] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [failedId, setFailedId] = useState<number | null>(null);
  const page = total === undefined ? selectedPage : Math.min(selectedPage, Math.max(0, Math.ceil(total / PAGE_SIZE) - 1));
  useEffect(() => {
    if (page < selectedPage) setSelectedPage(page);
  }, [page, selectedPage]);
  const { data, error, mutate } = useSWR<NotificationsResponse>(
    SWR_KEYS.notificationsPage(page, PAGE_SIZE, tab),
    errorHandlingFetcher
  );

  const dismiss = async (id: number) => {
    setBusyId(id);
    setFailedId(null);
    try {
      await dismissNotification(id);
      await invalidateNotificationCaches();
    } catch {
      setFailedId(id);
    } finally {
      setBusyId(null);
    }
  };

  if (error && !data) {
    return (
      <ResponsiveLayout className={`${card} flex flex-wrap items-center justify-between gap-3 p-5`} role="alert">
        <p className="text-sm text-text-05">{workspaceText("inboxItemsCouldNotBeLoaded")}</p>
        <ActionButton type="button" className={button} onClick={() => void mutate()}>{workspaceText("tryAgain")}</ActionButton>
      </ResponsiveLayout>
    );
  }
  if (!data) return <p role="status" className="text-sm text-text-03">{workspaceText("loadingInboxItems")}</p>;
  if (data.total_items === 0 && page === 0) return empty ?? null;

  const start = page * PAGE_SIZE + 1;
  const end = start + data.notifications.length - 1;
  return (
    <ResponsiveLayout display="flex" className="flex-col gap-3">
      {data.notifications.length > 0 && (
        <ul className={`${card} overflow-hidden`} aria-label={NOTIFICATION_LABEL[tab]}>
          {data.notifications.map((n) => {
            const context = inboxNotificationContext(n);
            const link = inboxNotificationLink(n);
            return (
              <li key={n.id} className="flex flex-wrap items-center gap-3 border-t border-border-01 px-5 py-4 first:border-t-0" data-testid="inbox-note">
                <div className="min-w-0 flex-1 break-words">
                  {context && <div className="mb-1 text-xs text-text-03">{context}</div>}
                  <div className="text-sm font-semibold text-text-05">{n.title}</div>
                  {n.description && <div className="mt-0.5 text-sm text-text-03">{n.description}</div>}
                  <div className="mt-1 text-xs text-text-03">{new Date(n.first_shown).toLocaleString()}</div>
                  {failedId === n.id && <p role="alert" className="mt-2 text-sm text-status-text-error-05">{workspaceText("couldnTDismissThisItemTryAgain")}</p>}
                </div>
                <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                  {link && <a href={link.href} className={button}>{link.label}</a>}
                  {tab !== "history" && !n.dismissed && (
                    <ActionButton type="button" onClick={() => void dismiss(n.id)} disabled={busyId !== null} className={button}>
                      {busyId === n.id ? "Dismissing…" : failedId === n.id ? "Retry dismissal" : "Dismiss"}
                    </ActionButton>
                  )}
                </ResponsiveLayout>
              </li>
            );
          })}
        </ul>
      )}
      {(page > 0 || data.has_more) && (
        <nav aria-label={`${NOTIFICATION_LABEL[tab]} pages`} className="flex flex-wrap items-center justify-between gap-3">
          <p aria-live="polite" className="text-sm text-text-03">
            {end >= start ? `${start}–${end} of ${data.total_items}` : "No items on this page"}
          </p>
          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
            <ActionButton type="button" className={button} disabled={page === 0 || busyId !== null} onClick={() => setSelectedPage(page - 1)}>{workspaceText("newer")}</ActionButton>
            <ActionButton type="button" className={button} disabled={!data.has_more || busyId !== null} onClick={() => setSelectedPage(page + 1)}>{workspaceText("older")}</ActionButton>
          </ResponsiveLayout>
        </nav>
      )}
    </ResponsiveLayout>
  );
}

export default function InboxPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [tab, setTab] = useState<Tab>("approve");
  const [showHistory, setShowHistory] = useState(false);
  const [showDismissed, setShowDismissed] = useState(false);
  const { data: totals, error: totalsError, mutate: refreshTotals } = useSWR<InboxNotificationSummary>(
    SWR_KEYS.inboxNotificationSummary, errorHandlingFetcher
  );
  const { data: live } = useSWR<{ items: unknown[] }>(useSettings()?.nortpole_craft_enabled === true ? SWR_KEYS.myLiveApprovals : null, errorHandlingFetcher, { refreshInterval: 15_000, shouldRetryOnError: false });
  const own = useOwnWork(30_000);
  const proposalCount = usePendingProposals().waiting.length;
  const { isAdmin } = useUser();
  const liveCount = live?.items.length ?? 0;
  const counts: Record<Tab, number> = {
    approve: own.plans.length + (totals?.approve ?? 0) + liveCount + proposalCount,
    review: own.drafts.length + (totals?.review ?? 0),
    updates: totals?.updates ?? 0,
  };

  const empty = (t: Tab) => (
    <section className={`${card} flex flex-col items-center p-8 text-center`} aria-labelledby="inbox-empty">
      <SvgEmpty size={96} aria-hidden="true" />
      <h2 id="inbox-empty" className="mb-1 text-base font-semibold text-text-05">{EMPTY[t].title}</h2>
      <p className="text-sm text-text-03">{EMPTY[t].body}</p>
    </section>
  );

  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-4xl flex-col gap-6 p-4 sm:p-8" data-testid="inbox-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">{workspaceText("inbox")}</h1>
        <p className="text-sm text-text-03">{workspaceText("whatIsWaitingForYouOpenAnItemTo")}</p>
      </header>

      <ResponsiveLayout display="flex" role="tablist" aria-label={workspaceText("inboxFilter")} className="gap-1 overflow-x-auto border-b border-border-01">
        {TABS.map((t) => (
          <ActionButton
            key={t.id}
            id={`inbox-tab-${t.id}`}
            role="tab" tabIndex={0}
            type="button"
            aria-selected={tab === t.id}
            aria-controls="inbox-panel"
            onClick={() => setTab(t.id)}
            className={`min-h-11 shrink-0 px-2.5 text-sm sm:px-4 font-semibold ${tab === t.id ? "border-b-2 border-text-05 text-text-05" : "text-text-03 hover:text-text-05"}`}
            data-testid={`inbox-tab-${t.id}`}
          >
            {t.label}
            {counts[t.id] > 0 && <>{" "}<span className="ml-1 rounded-full bg-background-neutral-02 px-2 py-0.5 text-xs">{counts[t.id]}<span className="sr-only"> waiting</span></span></>}
          </ActionButton>
        ))}
      </ResponsiveLayout>

      <ResponsiveLayout display="flex" id="inbox-panel" role="tabpanel" aria-labelledby={`inbox-tab-${tab}`} className="flex-col gap-4">
        {totalsError && !totals && (
          <ResponsiveLayout role="alert" className={`${card} flex flex-wrap items-center justify-between gap-3 p-5`}>
            <p className="text-sm text-text-05">{workspaceText("inboxCountsCouldNotBeLoaded")}</p>
            <ActionButton type="button" className={button} onClick={() => void refreshTotals()}>{workspaceText("retryCounts")}</ActionButton>
          </ResponsiveLayout>
        )}
        {tab === "approve" && (
          <>
            {isAdmin && <AdminWaiting />}
            <LiveApprovals />
            <IntegrationChanges />
            {own.plans.length > 0 && (
              <ul className={`${card} overflow-hidden`} aria-label={workspaceText("plansToAccept")}>
                {own.plans.map((t) => <TaskRow key={t.id} t={t} label={workspaceText("acceptThePlanToStartWork")} action="Review the plan" />)}
              </ul>
            )}
          </>
        )}
        {tab === "review" && own.drafts.length > 0 && (
          <ul className={`${card} overflow-hidden`} aria-label={workspaceText("draftsToReview")}>
            {own.drafts.map((t) => <TaskRow key={t.id} t={t} label={workspaceText("checkTheDraftAndItsSourcesBeforeApproving")} action="Review the draft" />)}
          </ul>
        )}
        <NotificationList key={tab} tab={tab} total={totals?.[tab]} empty={counts[tab] === 0 && empty(tab)} />
        {tab === "updates" && !!totals?.history && (
          <ResponsiveLayout display="flex" className="flex-col gap-3">
            <ActionButton type="button" className={`${button} self-start`} aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>
              {showHistory ? "Hide workflow history" : `Show workflow history (${totals.history})`}
            </ActionButton>
            {showHistory && <NotificationList tab="history" total={totals.history} />}
          </ResponsiveLayout>
        )}
        {tab === "updates" && !!totals?.dismissed && (
          <ResponsiveLayout display="flex" className="flex-col gap-3">
            <ActionButton type="button" className={`${button} self-start`} aria-expanded={showDismissed} onClick={() => setShowDismissed(!showDismissed)}>
              {showDismissed ? "Hide dismissed" : `Show dismissed (${totals.dismissed})`}
            </ActionButton>
            {showDismissed && <NotificationList tab="dismissed" total={totals.dismissed} />}
          </ResponsiveLayout>
        )}
      </ResponsiveLayout>
    </ResponsiveLayout>
  );
}

/** For administrators: what waits in admin Approvals, as one line with a link. Not counted in the Inbox numbers. */
function AdminWaiting() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const c = useApprovalCounts();
  if (!c.loaded || c.total === 0) return null;
  return (
    <section className={`${card} flex flex-wrap items-center justify-between gap-3 p-5`} aria-labelledby="inbox-admin" data-testid="inbox-admin-waiting">
      <div className="min-w-0">
        <h2 id="inbox-admin" className="text-sm font-semibold text-text-05">{workspaceText("asAnAdministrator")}</h2>
        <p className="text-sm text-text-03">{c.total} {c.total === 1 ? "item waits" : "items wait"}{" "}{workspaceText("inApprovals")}</p>
      </div>
      <NavLink href="/admin/approvals" className={button}>{workspaceText("openApprovals")}</NavLink>
    </section>
  );
}
