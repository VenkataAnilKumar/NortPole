import { inboxBadgeCount, inQuietHours, inboxNotificationLink } from "@/lib/notifications/inbox";
import { NotificationType, type Notification } from "@/lib/notifications/interfaces";

const base = { severity: "info", title: "t", description: null, first_shown: "", last_shown: "" };
const mk = (id: number, notif_type: NotificationType, dismissed = false): Notification =>
  ({ ...base, id, notif_type, dismissed }) as unknown as Notification;

const prefs = (over: Record<string, unknown> = {}) => ({
  approvals: true,
  run_updates: true,
  quiet_hours: { enabled: false, start: "22:00", end: "07:00" },
  ...over,
});
const at = (h: number, m = 0) => new Date(2026, 10, 11, h, m);

const counts = { approve: 2, review: 1, updates: 0, dismissed: 75, history: 40 };

describe("inQuietHours", () => {
  it("is off when disabled", () => {
    expect(inQuietHours({ enabled: false, start: "22:00", end: "07:00" }, at(23))).toBe(false);
  });
  it("handles a window that crosses midnight", () => {
    const q = { enabled: true, start: "22:00", end: "07:00" };
    expect(inQuietHours(q, at(23))).toBe(true);
    expect(inQuietHours(q, at(3))).toBe(true);
    expect(inQuietHours(q, at(7))).toBe(false);
    expect(inQuietHours(q, at(12))).toBe(false);
  });
  it("handles a same-day window", () => {
    const q = { enabled: true, start: "12:00", end: "13:30" };
    expect(inQuietHours(q, at(13))).toBe(true);
    expect(inQuietHours(q, at(14))).toBe(false);
  });
});

describe("inboxBadgeCount", () => {
  it("counts open actions and updates, never resolved items", () => {
    expect(inboxBadgeCount(counts, prefs(), at(12))).toBe(3);
  });
  it("leaves out actions when the person turned them off", () => {
    expect(inboxBadgeCount(counts, prefs({ approvals: false }), at(12))).toBe(1);
  });
  it("leaves out updates when turned off", () => {
    expect(inboxBadgeCount(counts, prefs({ run_updates: false }), at(12))).toBe(2);
  });
  it("holds updates but never actions during quiet hours", () => {
    const quiet = prefs({ quiet_hours: { enabled: true, start: "22:00", end: "07:00" } });
    expect(inboxBadgeCount(counts, quiet, at(23))).toBe(2);
  });
  it("counts live approvals as items that need action, and never holds them back", () => {
    const quiet = prefs({ quiet_hours: { enabled: true, start: "22:00", end: "07:00" } });
    expect(inboxBadgeCount(counts, prefs(), at(12), 2)).toBe(5);
    expect(inboxBadgeCount(counts, quiet, at(23), 2)).toBe(4);
    // The person's own plans to accept and drafts to review count as action items: shown in quiet hours, hidden
    // when approvals are switched off.
    expect(inboxBadgeCount(counts, prefs(), at(12), 0, 3)).toBe(6);
    expect(inboxBadgeCount(counts, quiet, at(23), 0, 3)).toBe(5);
    expect(inboxBadgeCount(counts, prefs({ approvals: false }), at(12), 0, 3)).toBe(1);
    expect(inboxBadgeCount(counts, prefs({ approvals: false }), at(12), 2)).toBe(1);
  });
});

describe("inboxNotificationLink", () => {
  it("opens an older document review by its message ID", () => {
    expect(inboxNotificationLink({
      ...mk(1, NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW),
      additional_data: { message_id: 42, chat_session_id: "chat" },
    })?.href).toBe("/app/workflows/runs?review=42");
  });

  it("opens the targeted plan when the notification also has a chat session", () => {
    expect(inboxNotificationLink({
      ...mk(1, NotificationType.WORKFLOW_PLAN_READY),
      additional_data: { task_id: "plan", chat_session_id: "chat" },
    })?.href).toBe("/app/workflows/drafts?task=plan");
  });
  it("opens the exact workflow run and retains direct workflow decision links", () => {
    expect(inboxNotificationLink({
      ...mk(1, NotificationType.WORKFLOW_RUN_FAILED),
      additional_data: { run_id: "run-1", schedule_id: "schedule", task_id: "task" },
    })?.href).toBe("/app/workflows/runs?run=run-1");
    expect(inboxNotificationLink({
      ...mk(2, NotificationType.WORKFLOW_DECISION_RECORDED),
      additional_data: { task_id: "task" },
    })?.href).toBe("/app/workflows/drafts?task=task");
  });

});
