import { NotificationType, type Notification } from "@/lib/notifications/interfaces";
import type { QuietHours, UserPreferences } from "@/lib/userPreferences/hooks";

/** Notification types that ask the reader to decide something. */
export const ACTION_TYPES = new Set<NotificationType>([
  NotificationType.APPROVAL_REQUESTED,
  NotificationType.SCHEDULED_TASK_AWAITING_APPROVAL,
  NotificationType.SCHEDULED_TASK_PRE_APPROVED_ACTION,
]);

export function isAction(n: Notification): boolean {
  return ACTION_TYPES.has(n.notif_type);
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
 * action too.
 */
export function inboxBadgeCount(
  notifications: Notification[],
  prefs: UserPreferences["notifications"],
  now: Date,
  liveApprovals = 0
): number {
  const open = notifications.filter((n) => !n.dismissed);
  const actions = prefs.approvals ? open.filter(isAction).length + liveApprovals : 0;
  const updates =
    prefs.run_updates && !inQuietHours(prefs.quiet_hours, now)
      ? open.filter((n) => !isAction(n)).length
      : 0;
  return actions + updates;
}
