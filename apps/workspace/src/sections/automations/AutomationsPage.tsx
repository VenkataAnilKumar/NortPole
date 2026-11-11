"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import type { ScheduledTaskListItem } from "@/app/craft/v1/tasks/types";

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";

function when(iso: string | null): string {
  if (!iso) return "Not scheduled";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "Not scheduled" : d.toLocaleString();
}

/**
 * Automations: tasks that run on a schedule. This lists the scheduled tasks the
 * backend already stores. Creating and editing stays with the existing editor
 * until the reviewed-workflow phase (A6) adds approval rules in this page.
 */
export default function AutomationsPage() {
  const { data, error, isLoading } = useSWR<ScheduledTaskListItem[]>(
    SWR_KEYS.scheduledTasks,
    errorHandlingFetcher
  );
  const tasks = Array.isArray(data) ? data : [];

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-8" data-testid="automations-page">
      <header className="flex flex-col gap-1">
        <h1 className="font-[family-name:var(--font-serif)] text-3xl font-medium text-text-05">Automations</h1>
        <p className="text-sm text-text-03">
          Tasks that run on a schedule. Anything that needs approval waits in your Inbox.
        </p>
      </header>

      {isLoading ? (
        <p className="text-sm text-text-03">Loading automations…</p>
      ) : error ? (
        <section className={card} role="alert" aria-labelledby="auto-unavailable">
          <h2 id="auto-unavailable" className="mb-1 text-base font-semibold text-text-05">
            Automations are not available here
          </h2>
          <p className="text-sm text-text-03">
            Scheduled tasks run in a sandbox that this build does not start. They appear here once that service is
            enabled for your workspace.
          </p>
        </section>
      ) : tasks.length === 0 ? (
        <section className={card} aria-labelledby="auto-empty">
          <h2 id="auto-empty" className="mb-1 text-base font-semibold text-text-05">No automations yet</h2>
          <p className="text-sm text-text-03">
            When you schedule a task it is listed here with its next run, its last result and whether it is paused.
          </p>
        </section>
      ) : (
        <ul className="flex flex-col gap-3">
          {tasks.map((t) => (
            <li key={t.id} className={card}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-text-05">{t.name}</h2>
                  <p className="text-sm text-text-03">{t.human_readable_schedule}</p>
                </div>
                <span className="shrink-0 rounded-full border border-border-01 px-2.5 py-0.5 text-xs font-medium text-text-03">
                  {t.status === "ACTIVE" ? "Active" : "Paused"}
                </span>
              </div>
              <dl className="mt-3 grid gap-1 text-sm text-text-03 sm:grid-cols-2">
                <div>
                  <dt className="inline font-medium text-text-05">Next run: </dt>
                  <dd className="inline">{when(t.next_run_at)}</dd>
                </div>
                <div>
                  <dt className="inline font-medium text-text-05">Last result: </dt>
                  <dd className="inline">{t.last_run ? t.last_run.status.replace("_", " ").toLowerCase() : "No runs yet"}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
