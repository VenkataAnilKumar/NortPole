"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useId, useState } from "react";
import { saveUserPreferences, useUserPreferences, type UserPreferences } from "@/lib/userPreferences/hooks";

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";

/**
 * Personal notification choices. These are stored and shown, but nothing sends
 * alerts outside the app yet: there is no email or chat channel in this build.
 * Alerts never carry source or report text.
 */
export default function NotificationsSettings() {
  const inputPrefix = useId();
  const workspaceText = useWorkspaceTranslations("workspaceUi");
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

  if (!prefs) return <p className="text-sm text-text-03">{workspaceText("loading")}</p>;
  const n = prefs.notifications;
  const set = (patch: Partial<UserPreferences["notifications"]>) =>
    update({ ...prefs, notifications: { ...n, ...patch } });

  const toggle = (id: string, label: string, help: string, checked: boolean, onChange: (v: boolean) => void) => (
    <ResponsiveLayout key={id} display="flex" className="min-h-12 items-start gap-3 py-2">
      <NativeInput id={inputPrefix + id} aria-describedby={inputPrefix + id + "-help"} type="checkbox" className="mt-1 h-4 w-4" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <label htmlFor={inputPrefix + id} className="block cursor-pointer text-sm font-medium text-text-05">{label}</label>
        <span id={inputPrefix + id + "-help"} className="block text-xs text-text-03">{help}</span>
      </span>
    </ResponsiveLayout>
  );

  return (
    <ResponsiveLayout display="flex" className="flex-col gap-6" data-testid="notifications-settings">
      <section className={card} aria-labelledby="ns-events">
        <h2 id="ns-events" className="mb-1 text-base font-semibold text-text-05">{workspaceText("whatToTellMeAbout")}</h2>
        <p className="mb-2 text-sm text-text-03">{workspaceText("alertsOnlySayThatSomethingNeedsYouTheyNever")}</p>
        {toggle("approvals", "Items that need my action", "Approvals waiting for you.", n.approvals, (v) => set({ approvals: v }))}
        {toggle("run_updates", "Task updates", "Finished, failed and scheduled runs.", n.run_updates, (v) => set({ run_updates: v }))}
      </section>

      <section className={card} aria-labelledby="ns-quiet">
        <h2 id="ns-quiet" className="mb-1 text-base font-semibold text-text-05">{workspaceText("quietHours")}</h2>
        <p className="mb-2 text-sm text-text-03">{workspaceText("holdNonUrgentAlertsDuringTheseHours")}</p>
        {toggle("quiet", "Use quiet hours", "", n.quiet_hours.enabled, (v) =>
          set({ quiet_hours: { ...n.quiet_hours, enabled: v } })
        )}
        <ResponsiveLayout display="flex" className="mt-2 flex-wrap items-center gap-3 text-sm text-text-05">
          <label className="flex items-center gap-2">{workspaceText("from")}<NativeInput
              type="time"
              value={n.quiet_hours.start}
              disabled={!n.quiet_hours.enabled}
              onChange={(e) => e.target.value && set({ quiet_hours: { ...n.quiet_hours, start: e.target.value } })}
              className="min-h-11 rounded-lg border border-border-01 bg-background-neutral-00 px-2"
            />
          </label>
          <label className="flex items-center gap-2">{workspaceText("to")}<NativeInput
              type="time"
              value={n.quiet_hours.end}
              disabled={!n.quiet_hours.enabled}
              onChange={(e) => e.target.value && set({ quiet_hours: { ...n.quiet_hours, end: e.target.value } })}
              className="min-h-11 rounded-lg border border-border-01 bg-background-neutral-00 px-2"
            />
          </label>
        </ResponsiveLayout>
      </section>

      {status === "saved" && <p role="status" className="text-sm text-status-success-05">{workspaceText("saved")}</p>}
      {status === "error" && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("couldNotSaveTryAgainInAMoment")}</p>}
      <p className="text-xs text-text-03">{workspaceText("theseChoicesAreSavedToYourAccountAndSet")}</p>
    </ResponsiveLayout>
  );
}
