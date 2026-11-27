import { NotificationType, type InboxNotificationSummary, type Notification } from "@/lib/notifications/interfaces";
import type { QuietHours, UserPreferences } from "@/lib/userPreferences/hooks";

const CONTEXT: Partial<Record<NotificationType, string>> = {
  [NotificationType.APPROVAL_REQUESTED]: "Craft approval request",
  [NotificationType.SCHEDULED_TASK_AWAITING_APPROVAL]: "Scheduled Craft task · Approval needed",
  [NotificationType.SCHEDULED_TASK_PRE_APPROVED_ACTION]: "Scheduled Craft task · Pre-approved action",
  [NotificationType.SCHEDULED_TASK_FAILED]: "Scheduled Craft task · Run failed",
  [NotificationType.WORKFLOW_DECISION_RECORDED]: "Workflow · Decision recorded",
  [NotificationType.WORKFLOW_PLAN_READY]: "Scheduled workflow · Plan ready",
  [NotificationType.WORKFLOW_RUN_NEEDS_REVIEW]: "Scheduled workflow · Review needed",
  [NotificationType.WORKFLOW_RUN_FAILED]: "Scheduled workflow · Run failed",
  [NotificationType.WORKFLOW_RUN_COMPLETE]: "Scheduled workflow · Run complete",
  [NotificationType.SCHEDULE_PAUSED]: "Scheduled workflow · Paused",
  [NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW]: "Document review · Findings to check",
  [NotificationType.SOURCE_REQUEST_DECIDED]: "Sources · Request decision",
  [NotificationType.SYSTEM_ANNOUNCEMENT]: "Workspace announcement",
};

export function inboxNotificationContext(n: Notification): string | undefined {
  const app = n.additional_data?.app_name;
  return n.notif_type === NotificationType.APPROVAL_REQUESTED && typeof app === "string" && app
    ? `Craft approval request · ${app}`
    : CONTEXT[n.notif_type];
}

export function inboxNotificationLink(n: Notification): { href: string; label: string } | null {
  const data = n.additional_data;
  const id = (key: string): string | null => {
    const value: unknown = data?.[key];
    return typeof value === "string" && value.trim() ? value : null;
  };
  const task = id("task_id");
  const schedule = id("schedule_id");
  const run = id("run_id");
  const session = id("chat_session_id");
  switch (n.notif_type) {
    case NotificationType.APPROVAL_REQUESTED: {
      const craftSession = id("session_id");
      return craftSession
        ? { href: `/craft/v1?sessionId=${encodeURIComponent(craftSession)}`, label: "Open Craft session" }
        : null;
    }
    case NotificationType.SCHEDULED_TASK_AWAITING_APPROVAL:
    case NotificationType.SCHEDULED_TASK_PRE_APPROVED_ACTION:
    case NotificationType.SCHEDULED_TASK_FAILED:
      return task ? { href: `/craft/v1/tasks/${encodeURIComponent(task)}`, label: "Open scheduled task" } : null;
    case NotificationType.SOURCE_REQUEST_DECIDED: {
      const request = id("request_id");
      return request
        ? { href: `/app/sources/discover#request-${encodeURIComponent(request)}`, label: "View request" }
        : null;
    }
    case NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW: {
      const message: unknown = data?.message_id;
      if (typeof message === "number" && Number.isSafeInteger(message) && message > 0) {
        return { href: `/app/workflows/runs?review=${message}`, label: "Review findings" };
      }
      return session ? { href: `/app?chatId=${encodeURIComponent(session)}`, label: "Open result" } : null;
    }
    case NotificationType.WORKFLOW_DECISION_RECORDED:
      return task ? { href: `/app/workflows/drafts?task=${encodeURIComponent(task)}`, label: "Open task" } : null;
    case NotificationType.WORKFLOW_PLAN_READY:
      if (task) return { href: `/app/workflows/drafts?task=${encodeURIComponent(task)}`, label: "Open plan" };
      return schedule ? { href: `/app/workflows/scheduled?schedule=${encodeURIComponent(schedule)}`, label: "Open schedule" } : null;
    case NotificationType.SCHEDULE_PAUSED:
      return schedule ? { href: `/app/workflows/scheduled?schedule=${encodeURIComponent(schedule)}`, label: "Open schedule" } : null;
    case NotificationType.WORKFLOW_RUN_NEEDS_REVIEW:
    case NotificationType.WORKFLOW_RUN_FAILED:
    case NotificationType.WORKFLOW_RUN_COMPLETE:
      if (run) return { href: `/app/workflows/runs?run=${encodeURIComponent(run)}`, label: "Open run" };
      if (task) {
        return {
          href: `/app/workflows/drafts?task=${encodeURIComponent(task)}`,
          label: "Open draft",
        };
      }
      if (session) {
        return { href: `/app?chatId=${encodeURIComponent(session)}`, label: "Open result" };
      }
      if (schedule) {
        return { href: `/app/workflows/scheduled?schedule=${encodeURIComponent(schedule)}`, label: "Open schedule" };
      }
      return null;
    default:
      return null;
  }
}

function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

/** True when `now` falls inside the quiet window. A window may cross midnight. */
export function inQuietHours(q: QuietHours, now: Date): boolean {
  if (!q.enabled) return false;
  const start = minutes(q.start);
  const end = minutes(q.end);
  if (start === end) return false;
  const cur = now.getHours() * 60 + now.getMinutes();
  return start < end ? cur >= start && cur < end : cur >= start || cur < end;
}

/**
 * The number shown on the Inbox tab. Items that need action count when the
 * person asked to be told about them, and are never held back by quiet hours.
 * Updates count only when asked for, and are held during quiet hours. Resolved
 * items never count. Live approvals waiting for a decision are items that need
 * action too, and so are the person's own plans to accept and drafts to review.
 */
export function inboxBadgeCount(
  counts: InboxNotificationSummary,
  prefs: UserPreferences["notifications"],
  now: Date,
  liveApprovals = 0,
  ownWork = 0
): number {
  const actions = prefs.approvals ? counts.approve + liveApprovals + ownWork : 0;
  const updates =
    prefs.run_updates && !inQuietHours(prefs.quiet_hours, now)
      ? counts.review + counts.updates
      : 0;
  return actions + updates;
}
