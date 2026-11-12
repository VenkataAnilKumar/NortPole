import { inboxBadgeCount, inQuietHours } from "@/lib/notifications/inbox";
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

const items = [
  mk(1, NotificationType.APPROVAL_REQUESTED),
  mk(2, NotificationType.APPROVAL_REQUESTED, true),
  mk(3, NotificationType.SCHEDULED_TASK_AWAITING_APPROVAL),
  mk(4, NotificationType.RELEASE_NOTES),
];

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
    expect(inboxBadgeCount(items, prefs(), at(12))).toBe(3);
  });
  it("leaves out actions when the person turned them off", () => {
    expect(inboxBadgeCount(items, prefs({ approvals: false }), at(12))).toBe(1);
  });
  it("leaves out updates when turned off", () => {
    expect(inboxBadgeCount(items, prefs({ run_updates: false }), at(12))).toBe(2);
  });
  it("holds updates but never actions during quiet hours", () => {
    const quiet = prefs({ quiet_hours: { enabled: true, start: "22:00", end: "07:00" } });
    expect(inboxBadgeCount(items, quiet, at(23))).toBe(2);
  });
  it("counts live approvals as items that need action, and never holds them back", () => {
    const quiet = prefs({ quiet_hours: { enabled: true, start: "22:00", end: "07:00" } });
    expect(inboxBadgeCount(items, prefs(), at(12), 2)).toBe(5);
    expect(inboxBadgeCount(items, quiet, at(23), 2)).toBe(4);
    expect(inboxBadgeCount(items, prefs({ approvals: false }), at(12), 2)).toBe(1);
  });
});
