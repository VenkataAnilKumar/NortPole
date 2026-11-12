"use client";

import { useState } from "react";
import { saveUserPreferences, useUserPreferences, type UserPreferences } from "@/lib/userPreferences/hooks";

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";

/**
 * Personal notification choices. These are stored and shown, but nothing sends
 * alerts outside the app yet: there is no email or chat channel in this build.
 * Alerts never carry source or report text.
 */
export default function NotificationsSettings() {
  const { data: prefs } = useUserPreferences();
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle");

  const update = async (next: UserPreferences) => {
    try {
      await saveUserPreferences(next);
      setStatus("saved");
    } catch {
      setStatus("error");
    }
    window.setTimeout(() => setStatus("idle"), 2500);
  };

  if (!prefs) return <p className="text-sm text-text-03">Loading…</p>;
  const n = prefs.notifications;
  const set = (patch: Partial<UserPreferences["notifications"]>) =>
    update({ ...prefs, notifications: { ...n, ...patch } });

  const toggle = (id: string, label: string, help: string, checked: boolean, onChange: (v: boolean) => void) => (
    <label key={id} className="flex min-h-12 cursor-pointer items-start gap-3 py-2">
      <input type="checkbox" className="mt-1 h-4 w-4" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="block text-sm font-medium text-text-05">{label}</span>
        <span className="block text-xs text-text-03">{help}</span>
      </span>
    </label>
  );

  return (
    <div className="flex flex-col gap-6" data-testid="notifications-settings">
      <section className={card} aria-labelledby="ns-events">
        <h2 id="ns-events" className="mb-1 text-base font-semibold text-text-05">What to tell me about</h2>
        <p className="mb-2 text-sm text-text-03">
          Alerts only say that something needs you. They never include source or report text.
        </p>
        {toggle("approvals", "Items that need my action", "Approvals waiting for you.", n.approvals, (v) => set({ approvals: v }))}
        {toggle("run_updates", "Task updates", "Finished, failed and scheduled runs.", n.run_updates, (v) => set({ run_updates: v }))}
      </section>

      <section className={card} aria-labelledby="ns-quiet">
        <h2 id="ns-quiet" className="mb-1 text-base font-semibold text-text-05">Quiet hours</h2>
        <p className="mb-2 text-sm text-text-03">Hold non-urgent alerts during these hours.</p>
        {toggle("quiet", "Use quiet hours", "", n.quiet_hours.enabled, (v) =>
          set({ quiet_hours: { ...n.quiet_hours, enabled: v } })
        )}
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-text-05">
          <label className="flex items-center gap-2">
            From
            <input
              type="time"
              value={n.quiet_hours.start}
              disabled={!n.quiet_hours.enabled}
              onChange={(e) => e.target.value && set({ quiet_hours: { ...n.quiet_hours, start: e.target.value } })}
              className="min-h-11 rounded-lg border border-border-01 bg-background-neutral-00 px-2"
            />
          </label>
          <label className="flex items-center gap-2">
            To
            <input
              type="time"
              value={n.quiet_hours.end}
              disabled={!n.quiet_hours.enabled}
              onChange={(e) => e.target.value && set({ quiet_hours: { ...n.quiet_hours, end: e.target.value } })}
              className="min-h-11 rounded-lg border border-border-01 bg-background-neutral-00 px-2"
            />
          </label>
        </div>
      </section>

      {status === "saved" && <p role="status" className="text-sm text-status-success-05">Saved.</p>}
      {status === "error" && <p role="alert" className="text-sm text-status-error-05">Could not save. Try again in a moment.</p>}
      <p className="text-xs text-text-03">
        These choices are saved to your account and set the number shown on the Inbox tab. The Inbox page itself
        still lists everything. Quiet hours hold task updates from that number, never items that need your action.
        Email and chat channels are not connected yet.
      </p>
    </div>
  );
}
