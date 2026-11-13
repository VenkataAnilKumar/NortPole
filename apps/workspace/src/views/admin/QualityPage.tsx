"use client";

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
  const r = d.runs;
  return (
    <div className="flex flex-col gap-5">
      <section className={card} aria-labelledby="q-runs">
        <h2 id="q-runs" className="text-base font-semibold text-text-05">Runs started in the last {d.window_days} days</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Started" value={r.totals.started} />
          <Stat label="Drafted" value={r.totals.drafted} />
          <Stat label="Failed" value={r.totals.failed} warn />
          <Stat label="Approved" value={r.totals.approved} />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label="Reached a draft, of those that ended" value={pct(r.draft_rate)} />
          <Stat label="Drafts that were approved" value={pct(r.approval_rate)} />
          <Stat label="Median time to a draft" value={dur(r.median_seconds_to_draft)} />
        </div>
      </section>
      <section className={card} aria-labelledby="q-packs">
        <h2 id="q-packs" className="mb-2 text-base font-semibold text-text-05">By workflow pack</h2>
        {r.by_pack.length === 0 ? (
          <p className="text-sm text-text-03">No runs started in this period.</p>
        ) : (
          <Scroll label="Runs by workflow pack">
            <table className="w-full text-sm">
              <thead><tr><th scope="col" className={th}>Pack</th><th scope="col" className={th}>Started</th><th scope="col" className={th}>Drafted</th><th scope="col" className={th}>Failed</th><th scope="col" className={th}>Approved</th></tr></thead>
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
        <h2 id="q-claims" className="text-base font-semibold text-text-05">Claims in those drafts</h2>
        <p className="mt-1 text-sm text-text-03">Counts only. A claim is a sentence; unsupported means it cites no source.</p>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Supported" value={r.claims.supported} />
          <Stat label="Unsupported" value={r.claims.unsupported} />
          <Stat label="Unsupported, removed by the reviewer" value={r.claims.removed} />
          <Stat label="Unsupported, still undecided" value={r.claims.undecided} />
        </div>
        <p className="mt-3 text-sm text-text-04">Unsupported share of claims: {pct(r.unsupported_share)}. Kept by the reviewer: {r.claims.kept}.</p>
      </section>
    </div>
  );
}

function Evals({ d }: { d: Quality }) {
  return (
    <section className={card} aria-labelledby="q-evals">
      <h2 id="q-evals" className="text-base font-semibold text-text-05">Pack evaluations by version and model</h2>
      <p className="mb-3 mt-1 text-sm text-text-03">The latest evaluation for each pack version and model. A pack is offered on a model only after it passes there; run evaluations from the Packs page.</p>
      {d.evals.length === 0 ? (
        <p className="text-sm text-text-03">No evaluations have been run yet.</p>
      ) : (
        <Scroll label="Pack evaluations">
          <table className="w-full text-sm">
            <thead><tr><th scope="col" className={th}>Pack</th><th scope="col" className={th}>Version</th><th scope="col" className={th}>Model</th><th scope="col" className={th}>Route</th><th scope="col" className={th}>Result</th><th scope="col" className={th}>Run</th></tr></thead>
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
  const f = d.feedback.chat;
  const r = d.runs.claims;
  return (
    <div className="flex flex-col gap-5">
      <section className={card} aria-labelledby="q-chat">
        <h2 id="q-chat" className="text-base font-semibold text-text-05">Chat answers rated in the last {d.window_days} days</h2>
        <p className="mt-1 text-sm text-text-03">Thumbs up and down on chat answers. The comments people type are not shown here.</p>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Thumbs up" value={f.positive} />
          <Stat label="Thumbs down" value={f.negative} warn />
          <Stat label="Said they needed a follow-up" value={f.needed_followup} />
          <Stat label="Share that were thumbs up" value={pct(f.positive_share)} />
        </div>
      </section>
      <section className={card} aria-labelledby="q-reviewer">
        <h2 id="q-reviewer" className="text-base font-semibold text-text-05">What reviewers did with drafts</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Drafts approved" value={d.runs.totals.approved} />
          <Stat label="Unsupported claims removed" value={r.removed} />
          <Stat label="Unsupported claims kept" value={r.kept} />
          <Stat label="Waiting for a decision" value={r.undecided} />
        </div>
      </section>
    </div>
  );
}

function Trends({ d }: { d: Quality }) {
  const max = Math.max(1, ...d.trends.map((t) => t.started));
  const rows = [...d.trends].reverse();
  return (
    <section className={card} aria-labelledby="q-trends">
      <h2 id="q-trends" className="text-base font-semibold text-text-05">Day by day, last {d.window_days} days</h2>
      <p className="mb-3 mt-1 text-sm text-text-03">Days are in UTC, newest first. The bar shows runs started that day.</p>
      <Scroll label="Daily trend">
        <table className="w-full text-sm">
          <thead><tr><th scope="col" className={th}>Day</th><th scope="col" className={th}>Started</th><th scope="col" className={th}>Drafted</th><th scope="col" className={th}>Approved</th><th scope="col" className={th}>Failed</th><th scope="col" className={th}>Refused</th></tr></thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.date} className="border-t border-border-01">
                <th scope="row" className={`${td} text-left whitespace-nowrap font-medium`}>{t.date}</th>
                <td className={td}>
                  <span className="inline-flex items-center gap-2">
                    <span aria-hidden="true" className="inline-block h-2 rounded-full bg-text-05" style={{ width: `${Math.round((t.started / max) * 80)}px` }} />
                    {t.started}
                  </span>
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
  const [tab, setTab] = useState<Tab>("Runs");
  const [days, setDays] = useState(30);
  const { data, error, isLoading } = useSWR<Quality>(`/api/admin/quality?days=${days}`, errorHandlingFetcher, { refreshInterval: 120000 });
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 p-4 sm:p-8" data-testid="quality-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-text-05">Quality</h1>
          <p className="mt-1 text-sm text-text-03">How reviewed work is going. Counts and rates only, never the content of anyone&apos;s work.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-text-04">
          Period
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-border-01 bg-background-neutral-00 px-2 py-1 text-text-05">
            <option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option>
          </select>
        </label>
      </div>
      <div role="tablist" aria-label="Quality views" className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t} type="button" role="tab" id={`qt-${t}`} aria-selected={tab === t} aria-controls="q-panel"
            onClick={() => setTab(t)}
            className={`min-h-11 rounded-full border px-4 text-sm ${tab === t ? "border-text-05 bg-background-neutral-01 font-semibold text-text-05" : "border-border-01 text-text-04"}`}
          >
            {t}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="text-sm text-status-text-error-05">The quality summary could not be loaded.</p>}
      {isLoading && <p className="text-sm text-text-03">Loading…</p>}
      {data && (
        <div role="tabpanel" id="q-panel" aria-labelledby={`qt-${tab}`}>
          {tab === "Runs" && <Runs d={data} />}
          {tab === "Evals" && <Evals d={data} />}
          {tab === "Feedback" && <Feedback d={data} />}
          {tab === "Trends" && <Trends d={data} />}
        </div>
      )}
    </div>
  );
}
