"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState } from "react";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface PackRuns { pack_id: string | null; started: number; drafted: number; failed: number; approved: number }
interface Quality {
  window_days: number;
  runs: {
    totals: { started: number; drafted: number; failed: number; approved: number };
    draft_rate: number | null; approval_rate: number | null; median_seconds_to_draft: number | null;
    by_pack: PackRuns[];
    claims: { supported: number; unsupported: number; notice: number; kept: number; removed: number; undecided: number };
    unsupported_share: number | null;
  };
  evals: { pack_id: string; version: string; model: string; route_kind: string; passed: boolean; cases_passed: number; cases_total: number; failed_questions: string[]; run_at: string }[];
  feedback: { chat: { positive: number; negative: number; needed_followup: number; positive_share: number | null } };
  trends: { date: string; started: number; drafted: number; approved: number; failed: number; refused: number }[];
  scheduled?: {
    runs: number; plans: number; accepted: number; accepted_rate: number | null; failed_or_skipped: number;
    auto_paused_schedules: number; input_tokens: number; output_tokens: number; active_schedules: number;
  };
}

const TABS = ["Runs", "Evals", "Feedback", "Trends"] as const;
type Tab = (typeof TABS)[number];
const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const th = "py-2 pr-3 text-left font-medium text-text-03";
const td = "py-2 pr-3 text-text-05";
const pct = (r: number | null) => (r === null ? "no data" : `${Math.round(r * 100)}%`);
const dur = (s: number | null) => (s === null ? "no data" : s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`);

function Stat({ label, value, warn }: { label: string; value: string | number; warn?: boolean }) {
  return (
    <div className="rounded-xl bg-background-neutral-01 p-3" data-testid="q-stat">
      <div className={`text-2xl font-semibold ${warn && Number(value) > 0 ? "text-status-text-error-05" : "text-text-05"}`}>{value}</div>
      <div className="text-xs text-text-04">{label}</div>
    </div>
  );
}

function Scroll({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}

function Runs({ d }: { d: Quality }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const r = d.runs;
  return (
    <ResponsiveLayout display="flex" className="flex-col gap-5">
      <section className={card} aria-labelledby="q-runs">
        <h2 id="q-runs" className="text-base font-semibold text-text-05">{workspaceText("runsStartedInTheLast")}{" "}{d.window_days} days</h2>
        <ResponsiveLayout display="grid" className="mt-3 grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={workspaceText("started")} value={r.totals.started} />
          <Stat label={workspaceText("drafted")} value={r.totals.drafted} />
          <Stat label={workspaceText("failed")} value={r.totals.failed} warn />
          <Stat label={workspaceText("approved")} value={r.totals.approved} />
        </ResponsiveLayout>
        <ResponsiveLayout display="grid" className="mt-3 grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label={workspaceText("reachedADraftOfThoseThatEnded")} value={pct(r.draft_rate)} />
          <Stat label={workspaceText("draftsThatWereApproved")} value={pct(r.approval_rate)} />
          <Stat label={workspaceText("medianTimeToADraft")} value={dur(r.median_seconds_to_draft)} />
        </ResponsiveLayout>
      </section>
      <section className={card} aria-labelledby="q-packs">
        <h2 id="q-packs" className="mb-2 text-base font-semibold text-text-05">{workspaceText("byWorkflowPack")}</h2>
        {r.by_pack.length === 0 ? (
          <p className="text-sm text-text-03">{workspaceText("noRunsStartedInThisPeriod")}</p>
        ) : (
          <Scroll label={workspaceText("runsByWorkflowPack")}>
            <table className="w-full text-sm">
              <thead><tr><th scope="col" className={th}>{workspaceText("pack")}</th><th scope="col" className={th}>{workspaceText("started")}</th><th scope="col" className={th}>{workspaceText("drafted")}</th><th scope="col" className={th}>{workspaceText("failed")}</th><th scope="col" className={th}>{workspaceText("approved")}</th></tr></thead>
              <tbody>
                {r.by_pack.map((p) => (
                  <tr key={p.pack_id ?? "own"} className="border-t border-border-01">
                    <th scope="row" className={`${td} text-left font-medium`}>{p.pack_id ?? "Own request (no pack)"}</th>
                    <td className={td}>{p.started}</td><td className={td}>{p.drafted}</td><td className={td}>{p.failed}</td><td className={td}>{p.approved}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Scroll>
        )}
      </section>
      <section className={card} aria-labelledby="q-claims">
        <h2 id="q-claims" className="text-base font-semibold text-text-05">{workspaceText("claimsInThoseDrafts")}</h2>
        <p className="mt-1 text-sm text-text-03">{workspaceText("countsOnlyAClaimIsASentenceUnsupportedMeans")}</p>
        <ResponsiveLayout display="grid" className="mt-3 grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={workspaceText("supported")} value={r.claims.supported} />
          <Stat label={workspaceText("unsupported")} value={r.claims.unsupported} />
          <Stat label={workspaceText("unsupportedRemovedByTheReviewer")} value={r.claims.removed} />
          <Stat label={workspaceText("unsupportedStillUndecided")} value={r.claims.undecided} />
        </ResponsiveLayout>
        <p className="mt-3 text-sm text-text-04">{workspaceText("unsupportedShareOfClaims")}{" "}{pct(r.unsupported_share)}{workspaceText("keptByTheReviewer")}{" "}{r.claims.kept}.</p>
      </section>
      {d.scheduled && (
        <section className={card} aria-labelledby="q-scheduled" data-testid="q-scheduled">
          <h2 id="q-scheduled" className="text-base font-semibold text-text-05">{workspaceText("scheduledWorkflows")}</h2>
          <p className="mt-1 text-sm text-text-03">{workspaceText("eachScheduledRunDraftsAPlanAndWaitsFor")}</p>
          <ResponsiveLayout display="grid" className="mt-3 grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={workspaceText("activeSchedules")} value={d.scheduled.active_schedules} />
            <Stat label={workspaceText("runsInThePeriod")} value={d.scheduled.runs} />
            <Stat label={workspaceText("plansAccepted")} value={`${d.scheduled.accepted} of ${d.scheduled.plans}`} />
            <Stat label={workspaceText("pausedByTheRules")} value={d.scheduled.auto_paused_schedules} warn />
          </ResponsiveLayout>
          <p className="mt-3 text-sm text-text-04">{workspaceText("plansAccepted_9b492a")}{" "}{pct(d.scheduled.accepted_rate)}{workspaceText("runsThatFailedOrWereSkipped")}{" "}{d.scheduled.failed_or_skipped}{workspaceText("tokensUsedByScheduledPlanning")}{" "}
            {d.scheduled.input_tokens.toLocaleString()} in, {d.scheduled.output_tokens.toLocaleString()}{" "}{workspaceText("outCostsByRouteAreOnTheRoutePolicy")}</p>
        </section>
      )}
    </ResponsiveLayout>
  );
}

function Evals({ d }: { d: Quality }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  return (
    <section className={card} aria-labelledby="q-evals">
      <h2 id="q-evals" className="text-base font-semibold text-text-05">{workspaceText("packEvaluationsByVersionAndModel")}</h2>
      <p className="mb-3 mt-1 text-sm text-text-03">{workspaceText("theLatestEvaluationForEachPackVersionAndModel")}</p>
      {d.evals.length === 0 ? (
        <p className="text-sm text-text-03">{workspaceText("noEvaluationsHaveBeenRunYet")}</p>
      ) : (
        <Scroll label={workspaceText("packEvaluations")}>
          <table className="w-full text-sm">
            <thead><tr><th scope="col" className={th}>{workspaceText("pack")}</th><th scope="col" className={th}>{workspaceText("version_2da600")}</th><th scope="col" className={th}>{workspaceText("model")}</th><th scope="col" className={th}>{workspaceText("route_499952")}</th><th scope="col" className={th}>{workspaceText("result")}</th><th scope="col" className={th}>{workspaceText("run")}</th></tr></thead>
            <tbody>
              {d.evals.map((e) => (
                <tr key={`${e.pack_id}-${e.version}-${e.model}`} className="border-t border-border-01 align-top">
                  <th scope="row" className={`${td} text-left font-medium`}>{e.pack_id}</th>
                  <td className={td}>{e.version}</td><td className={td}>{e.model}</td><td className={td}>{e.route_kind}</td>
                  <td className={td}>
                    <span className={e.passed ? "text-text-05" : "text-status-text-error-05"}>{e.passed ? "Passed" : "Failed"}</span>{" "}
                    <span className="text-text-03">{e.cases_passed} of {e.cases_total} {e.cases_total === 1 ? "case" : "cases"}</span>
                    {e.failed_questions.length > 0 && (
                      <ul className="mt-1 list-disc pl-4 text-xs text-text-03">{e.failed_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
                    )}
                  </td>
                  <td className={`${td} whitespace-nowrap`}>{new Date(e.run_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
      )}
    </section>
  );
}

function Feedback({ d }: { d: Quality }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const f = d.feedback.chat;
  const r = d.runs.claims;
  return (
    <ResponsiveLayout display="flex" className="flex-col gap-5">
      <section className={card} aria-labelledby="q-chat">
        <h2 id="q-chat" className="text-base font-semibold text-text-05">{workspaceText("chatAnswersRatedInTheLast")}{" "}{d.window_days} days</h2>
        <p className="mt-1 text-sm text-text-03">{workspaceText("thumbsUpAndDownOnChatAnswersTheComments")}</p>
        <ResponsiveLayout display="grid" className="mt-3 grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={workspaceText("thumbsUp")} value={f.positive} />
          <Stat label={workspaceText("thumbsDown")} value={f.negative} warn />
          <Stat label={workspaceText("saidTheyNeededAFollowUp")} value={f.needed_followup} />
          <Stat label={workspaceText("shareThatWereThumbsUp")} value={pct(f.positive_share)} />
        </ResponsiveLayout>
      </section>
      <section className={card} aria-labelledby="q-reviewer">
        <h2 id="q-reviewer" className="text-base font-semibold text-text-05">{workspaceText("whatReviewersDidWithDrafts")}</h2>
        <ResponsiveLayout display="grid" className="mt-3 grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={workspaceText("draftsApproved")} value={d.runs.totals.approved} />
          <Stat label={workspaceText("unsupportedClaimsRemoved")} value={r.removed} />
          <Stat label={workspaceText("unsupportedClaimsKept")} value={r.kept} />
          <Stat label={workspaceText("waitingForADecision")} value={r.undecided} />
        </ResponsiveLayout>
      </section>
    </ResponsiveLayout>
  );
}

function Trends({ d }: { d: Quality }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const max = Math.max(1, ...d.trends.map((t) => t.started));
  const rows = [...d.trends].reverse();
  return (
    <section className={card} aria-labelledby="q-trends">
      <h2 id="q-trends" className="text-base font-semibold text-text-05">{workspaceText("dayByDayLast")}{" "}{d.window_days} days</h2>
      <p className="mb-3 mt-1 text-sm text-text-03">{workspaceText("daysAreInUtcNewestFirstTheBarShows")}</p>
      <Scroll label={workspaceText("dailyTrend")}>
        <table className="w-full text-sm">
          <thead><tr><th scope="col" className={th}>{workspaceText("day")}</th><th scope="col" className={th}>{workspaceText("started")}</th><th scope="col" className={th}>{workspaceText("drafted")}</th><th scope="col" className={th}>{workspaceText("approved")}</th><th scope="col" className={th}>{workspaceText("failed")}</th><th scope="col" className={th}>{workspaceText("refused")}</th></tr></thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.date} className="border-t border-border-01">
                <th scope="row" className={`${td} text-left whitespace-nowrap font-medium`}>{t.date}</th>
                <td className={td}>
                  <ResponsiveLayout as="span" display="inlineFlex" className="items-center gap-2">
                    <span aria-hidden="true" className="inline-block h-2 rounded-full bg-text-05" style={{ width: `${Math.round((t.started / max) * 80)}px` }} />
                    {t.started}
                  </ResponsiveLayout>
                </td>
                <td className={td}>{t.drafted}</td><td className={td}>{t.approved}</td>
                <td className={`${td} ${t.failed ? "text-status-text-error-05" : ""}`}>{t.failed}</td><td className={td}>{t.refused}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
    </section>
  );
}

/** Run quality: counts, rates and durations only. Never the title, request, draft or comment text of anyone's work. */
export default function QualityPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [tab, setTab] = useState<Tab>("Runs");
  const [days, setDays] = useState(30);
  const { data, error, isLoading } = useSWR<Quality>(`/api/admin/quality?days=${days}`, errorHandlingFetcher, { refreshInterval: 120000 });
  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-5xl flex-col gap-5 p-4 sm:p-8" data-testid="quality-page">
      <ResponsiveLayout display="flex" className="flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-text-05">{workspaceText("quality")}</h1>
          <p className="mt-1 text-sm text-text-03">{workspaceText("howReviewedWorkIsGoingCountsAndRatesOnly")}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-text-04">{workspaceText("period")}<NativeSelect value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-border-01 bg-background-neutral-00 px-2 py-1 text-text-05">
            <option value={7}>{workspaceText("7Days")}</option><option value={30}>{workspaceText("30Days")}</option><option value={90}>{workspaceText("90Days")}</option>
          </NativeSelect>
        </label>
      </ResponsiveLayout>
      <ResponsiveLayout display="flex" role="tablist" aria-label={workspaceText("qualityViews")} className="flex-wrap gap-2">
        {TABS.map((t) => (
          <ActionButton
            key={t} type="button" role="tab" tabIndex={0} id={`qt-${t}`} aria-selected={tab === t} aria-controls="q-panel"
            onClick={() => setTab(t)}
            className={`min-h-11 rounded-full border px-4 text-sm ${tab === t ? "border-text-05 bg-background-neutral-01 font-semibold text-text-05" : "border-border-01 text-text-04"}`}
          >
            {t}
          </ActionButton>
        ))}
      </ResponsiveLayout>
      {error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("theQualitySummaryCouldNotBeLoaded")}</p>}
      {isLoading && <p className="text-sm text-text-03">{workspaceText("loading")}</p>}
      {data && (
        <div role="tabpanel" id="q-panel" aria-labelledby={`qt-${tab}`}>
          {tab === "Runs" && <Runs d={data} />}
          {tab === "Evals" && <Evals d={data} />}
          {tab === "Feedback" && <Feedback d={data} />}
          {tab === "Trends" && <Trends d={data} />}
        </div>
      )}
    </ResponsiveLayout>
  );
}
