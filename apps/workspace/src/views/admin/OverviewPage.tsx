"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { useApprovalCounts } from "@/lib/approvals";

interface Overview {
  window_days: number;
  runs: { failed_plans: number; failed_runs: number; drafts_ready: number; approved: number; recent_errors: { state: string; error: string; at: string }[] };
  refusals: { total: number; by_action: { action: string; count: number }[]; recent: { action: string; summary: string; at: string }[] };
  packs: { active: number; unavailable: { pack_id: string; name: string; version: string; reason: string }[] };
  audit_chain: { ok: boolean; checked: number; unhashed_rows: number; first_break: { id: number; reason: string } | null };
  setup: { item: string; ok: boolean; note: string; href: string }[];
}

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const when = (iso: string) => new Date(iso).toLocaleString();

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="rounded-xl bg-background-neutral-01 p-3" data-testid="ov-stat">
      <div className={`text-2xl font-semibold ${warn && value > 0 ? "text-status-text-error-05" : "text-text-05"}`}>{value}</div>
      <div className="text-xs text-text-04">{label}</div>
    </div>
  );
}

/** What needs an administrator's attention now. Counts, reasons and system messages only: never the title or text of anyone's task. */
export default function OverviewPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data, error, isLoading } = useSWR<Overview>("/api/admin/overview", errorHandlingFetcher, { refreshInterval: 60000 });
  const approvals = useApprovalCounts();
  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-5xl flex-col gap-5 p-4 sm:p-8" data-testid="overview-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("overview")}</h1>
        <p className="mt-1 text-sm text-text-03">{workspaceText("whatNeedsAttention")}{data ? ` in the last ${data.window_days} days` : ""}{workspaceText("itShowsCountsAndReasonsNeverTheContentOf")}</p>
      </div>
      {error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("theOverviewCouldNotBeLoaded")}</p>}
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loading")}</p>}
      {approvals.loaded && (
        <section className={card} aria-labelledby="ov-approvals" data-testid="overview-approvals">
          <ResponsiveLayout display="flex" className="flex-wrap items-baseline justify-between gap-2">
            <h2 id="ov-approvals" className="text-base font-semibold text-text-05">{workspaceText("waitingForAnAdministrator")}</h2>
            <NavLink href="/admin/approvals" className="text-sm font-semibold text-text-05 underline">{workspaceText("openApprovals")}</NavLink>
          </ResponsiveLayout>
          <p className="mt-1 text-sm text-text-04">
            {approvals.total === 0
              ? "Nothing is waiting."
              : `${approvals.sends} ${approvals.sends === 1 ? "send" : "sends"}, ${approvals.changes} administrator ${approvals.changes === 1 ? "change" : "changes"}, ${approvals.tools} tool ${approvals.tools === 1 ? "definition" : "definitions"}, ${approvals.requests} ${approvals.requests === 1 ? "request" : "requests"} from people.`}
          </p>
        </section>
      )}
      {data && (
        <>
          <section className={card} aria-labelledby="ov-runs">
            <h2 id="ov-runs" className="text-base font-semibold text-text-05">{workspaceText("tasks")}</h2>
            <ResponsiveLayout display="grid" className="mt-3 grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label={workspaceText("plansThatFailed")} value={data.runs.failed_plans} warn />
              <Stat label={workspaceText("runsThatFailed")} value={data.runs.failed_runs} warn />
              <Stat label={workspaceText("draftsWaitingForReview")} value={data.runs.drafts_ready} />
              <Stat label={workspaceText("approved")} value={data.runs.approved} />
            </ResponsiveLayout>
            {data.runs.recent_errors.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1 text-sm text-text-04" aria-label={workspaceText("recentFailures")}>
                {data.runs.recent_errors.map((e, i) => (
                  <li key={i}><span className="text-text-03">{when(e.at)}</span> · {e.state === "plan_failed" ? "plan" : "run"}: {e.error}</li>
                ))}
              </ul>
            )}
          </section>

          <section className={card} aria-labelledby="ov-refusals">
            <ResponsiveLayout display="flex" className="flex-wrap items-baseline justify-between gap-2">
              <h2 id="ov-refusals" className="text-base font-semibold text-text-05">{workspaceText("refusedRequests")}</h2>
              <NavLink href="/admin/audit" className="text-sm font-semibold text-text-05 underline">{workspaceText("openTheAuditLog")}</NavLink>
            </ResponsiveLayout>
            <p className="mt-1 text-sm text-text-04">
              {data.refusals.total === 0 ? "Nothing was refused." : `${data.refusals.total} refused: ` + data.refusals.by_action.map((a) => `${a.action} ${a.count}`).join(", ") + "."}
            </p>
            {data.refusals.recent.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1 text-sm text-text-04">
                {data.refusals.recent.map((r, i) => (
                  <li key={i}><span className="text-text-03">{when(r.at)}</span> · {r.summary}</li>
                ))}
              </ul>
            )}
          </section>

          <ResponsiveLayout display="grid" className="gap-5 lg:grid-cols-2">
            <section className={card} aria-labelledby="ov-packs">
              <h2 id="ov-packs" className="text-base font-semibold text-text-05">{workspaceText("packs")}</h2>
              <p className="mt-1 text-sm text-text-04">
                {data.packs.active} active.{" "}
                {data.packs.unavailable.length === 0 ? "All are available on the current model." : `${data.packs.unavailable.length} not available to people:`}
              </p>
              <ul className="mt-2 flex flex-col gap-1 text-sm text-text-04">
                {data.packs.unavailable.map((p) => (
                  <li key={p.pack_id} className="text-status-text-error-05">{p.name} {p.version}: {p.reason}.</li>
                ))}
              </ul>
            </section>
            <section className={card} aria-labelledby="ov-chain">
              <h2 id="ov-chain" className="text-base font-semibold text-text-05">{workspaceText("auditLogIntegrity")}</h2>
              <p className={`mt-1 text-sm ${data.audit_chain.ok ? "text-text-04" : "text-status-text-error-05"}`} data-testid="ov-chain">
                {data.audit_chain.ok
                  ? `Intact: ${data.audit_chain.checked} events checked.`
                  : `Broken at event ${data.audit_chain.first_break?.id}: ${data.audit_chain.first_break?.reason}.`}
                {data.audit_chain.unhashed_rows ? ` ${data.audit_chain.unhashed_rows} older events predate the chain.` : ""}
              </p>
            </section>
          </ResponsiveLayout>

          <section className={card} aria-labelledby="ov-setup">
            <h2 id="ov-setup" className="text-base font-semibold text-text-05">{workspaceText("setup")}</h2>
            <ul className="mt-2 flex flex-col divide-y divide-border-01">
              {data.setup.map((x) => (
                <li key={x.item} className="flex flex-wrap items-baseline justify-between gap-2 py-2" data-testid="ov-setup-row">
                  <div className="min-w-0 text-sm">
                    <span className={`font-semibold ${x.ok ? "text-text-05" : "text-status-text-error-05"}`}>{x.ok ? "" : "Needs attention: "}{x.item}</span>
                    <span className="text-text-04"> · {x.note}</span>
                  </div>
                  <a href={x.href} className="text-sm font-semibold text-text-05 underline">{workspaceText("open")}</a>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </ResponsiveLayout>
  );
}
