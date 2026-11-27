"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeSelect, NativeTextArea } from "@opal/components";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useId, useRef, useState } from "react";
import { useFormatter } from "next-intl";
import useSWR, { mutate as mutateCache } from "swr";
import { Button } from "@opal/components";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { invalidateNotificationCaches } from "@/lib/notifications/api";
import DocumentRevisionForm from "./DocumentRevisionForm";

type Action = "revision_requested" | "exception_accepted" | "resolved";

const actions: Record<Action, { label: string; past: string }> = {
  revision_requested: { label: "Request a revision", past: "Revision requested" },
  exception_accepted: { label: "Accept an exception", past: "Exception accepted" },
  resolved: { label: "Resolve after checking", past: "Resolved" },
};

const statusLabels = {
  aligned: "Aligned with policy",
  conflict: "Potential conflict",
  needs_review: "Needs a human decision",
};

interface Decision {
  id: number;
  action: Action;
  reason: string;
  created_at: string;
}

interface Finding {
  number: number;
  status: keyof typeof statusLabels;
  explanation: string;
  document_quote: string;
  policy_quote: string;
  citation: { number: number; title: string; link: string | null } | null;
  decisions: Decision[];
  is_open: boolean;
}

interface Review {
  message_id: number;
  chat_session_id: string;
  file_name: string | null;
  created_at: string;
  pack_name: string | null;
  open_findings: number | null;
  findings: Finding[];
  context: { library_name: string } | null;
  can_review_revision: boolean;
  revised_reviews: number[];
  revision: {
    previous_id: number;
    findings: { previous_number: number; revised_number: number | null; addressed: boolean }[];
    new_findings: number[];
  } | null;
}

const control = "rounded-lg border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";
const textLink = "text-sm font-medium text-text-05 underline underline-offset-2";

function DecisionForm({ reviewId, finding, onSaved, onConflict }: {
  reviewId: number;
  finding: Finding;
  onSaved: (review: Review) => void;
  onConflict: () => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [action, setAction] = useState<Action | "">("");
  const decisionId = useId();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const attempt = useRef<{ payload: string; id: string } | null>(null);
  const latest = finding.decisions[0];

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || !action || (action === "exception_accepted" && !reason.trim())) return;
    setBusy(true);
    setError("");
    const data = { expected_latest_id: latest?.id ?? null, action, reason: reason.trim() };
    const payload = JSON.stringify(data);
    try {
      if (attempt.current?.payload !== payload) attempt.current = { payload, id: crypto.randomUUID() };
      const response = await fetch(`/api/chat/document-reviews/${reviewId}/findings/${finding.number}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, request_id: attempt.current.id }),
      });
      if (!response.ok) {
        if (response.status === 409) onConflict();
        const failure = await response.json().catch(() => null);
        throw new Error(typeof failure?.detail === "string" ? failure.detail : "Could not save the decision.");
      }
      onSaved(await response.json());
      attempt.current = null;
      setAction("");
      setReason("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save the decision.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="mt-4 grid gap-2" aria-label={`Decision for finding ${finding.number}`}>
      <ResponsiveLayout display="grid" className="gap-1 text-sm font-medium text-text-05 sm:max-w-xs">
        <label htmlFor={decisionId}>{workspaceText("decision")}</label>
        <NativeSelect id={decisionId} className={control} value={action} disabled={busy} onChange={(event) => setAction(event.target.value as Action | "")}>
          <option value="">{workspaceText("chooseADecision")}</option>
          {Object.entries(actions).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
        </NativeSelect>
      </ResponsiveLayout>
      {action && (
        <label className="grid gap-1 text-sm text-text-05">
          {action === "exception_accepted" ? "Reason (required)" : "Reason (optional)"}
          <NativeTextArea className={control} rows={2} maxLength={1000} required={action === "exception_accepted"}
            disabled={busy} value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
      )}
      <ResponsiveLayout display="flex" className="items-center gap-3">
        <Button type="submit" disabled={busy || !action || (action === "exception_accepted" && !reason.trim())}>
          {busy ? "Saving…" : "Save decision"}
        </Button>
        {error && <p role="alert" className="text-sm text-status-text-error-05">{error}</p>}
      </ResponsiveLayout>
    </form>
  );
}

export default function DocumentReviewDetails({ reviewId }: { reviewId: number }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const date = useFormatter();
  const [message, setMessage] = useState("");
  const { data, error, mutate } = useSWR<Review>(`/api/chat/document-reviews/${reviewId}`, errorHandlingFetcher);
  const saved = (review: Review) => {
    void mutate(review);
    void mutateCache((key) => typeof key === "string" && key.startsWith("/api/chat/workflow-run-feed"));
    void invalidateNotificationCaches();
    setMessage("Decision saved.");
  };

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-5 p-4 sm:p-8" aria-labelledby="document-review-heading">
      <NavLink href="/app/workflows/runs" className={textLink}>{workspaceText("backToRuns")}</NavLink>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 id="document-review-heading" className="text-2xl font-semibold text-text-05">{workspaceText("documentReview")}</h1>
          {data && <p className="mt-1 break-words text-sm text-text-03">{data.file_name ?? "Document"}{data.pack_name && ` · ${data.pack_name}`}</p>}
        </div>
        {data && <NavLink href={`/app?chatId=${data.chat_session_id}`} className={textLink}>{workspaceText("openChatReport")}</NavLink>}
      </header>
      {error ? (
        <p role="alert" className="text-sm text-text-03">{workspaceText("thisReviewIsUnavailable")}</p>
      ) : !data ? (
        <output className="text-sm text-text-03">{workspaceText("loadingFindings")}</output>
      ) : data.open_findings === null ? (
        <p className="text-sm text-text-03">{workspaceText("thisReviewWasSavedBeforeFindingDecisionsWereAvailable")}</p>
      ) : (
        <>
          <p className="text-sm font-medium text-text-05">
            {data.open_findings === 1 ? "1 open finding" : `${data.open_findings} open findings`}
          </p>
          <p role="status" className="sr-only">{message}</p>
          {data.revision && (
            <section aria-labelledby="revision-comparison" className="grid gap-2 rounded-xl border border-border-01 p-4 text-sm text-text-03">
              <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-2">
                <h2 id="revision-comparison" className="font-semibold text-text-05">{workspaceText("changesFromThePreviousReview")}</h2>
                <NavLink href={`/app/workflows/runs?review=${data.revision.previous_id}`} className={textLink}>{workspaceText("previousReview")}</NavLink>
              </ResponsiveLayout>
              <ul className="grid gap-1">
                {data.revision.findings.map((item) => (
                  <li key={item.previous_number}>
                    <NavLink href={`/app/workflows/runs?review=${data.revision!.previous_id}#finding-${item.previous_number}`} className={textLink}>{workspaceText("previousFinding")}{" "}{item.previous_number}
                    </NavLink>
                    {" · "}{item.addressed ? "Appears addressed" : "Still open"}
                    {item.revised_number && <>{" · "}<NavLink href={`#finding-${item.revised_number}`} className={textLink}>{workspaceText("revisedFinding")}{" "}{item.revised_number}</NavLink></>}
                  </li>
                ))}
                {data.revision.new_findings.map((number) => (
                  <li key={`new-${number}`}>{workspaceText("new")}{" "}<NavLink href={`#finding-${number}`} className={textLink}>{workspaceText("finding")}{" "}{number}</NavLink></li>
                ))}
              </ul>
              <p>{workspaceText("reviewTheEvidenceBeforeClosingAFindingInThe")}</p>
            </section>
          )}
          {!!data.revised_reviews?.length && (
            <ResponsiveLayout display="flex" className="flex-wrap gap-3">
              {data.revised_reviews.map((id, index) => (
                <NavLink key={id} href={`/app/workflows/runs?review=${id}`} className={textLink}>
                  {index === 0 ? "Latest revised review" : `Earlier revised review ${data.revised_reviews.length - index}`}
                </NavLink>
              ))}
            </ResponsiveLayout>
          )}
          {data.can_review_revision && data.context && (
            <DocumentRevisionForm reviewId={reviewId} library={data.context.library_name} pack={data.pack_name} />
          )}
          {!data.context && data.findings.some((finding) => finding.decisions[0]?.action === "revision_requested") && (
            <p className="text-sm text-text-03">{workspaceText("thisReportPredatesSavedReviewSettingsStartANew")}</p>
          )}
          <ol className="grid gap-3" aria-label={workspaceText("reviewFindings")}>
            {data.findings.map((finding) => {
              const latest = finding.decisions[0];
              const external = finding.citation?.link?.match(/^https?:\/\//i);
              return (
                <li key={finding.number} id={`finding-${finding.number}`} className="min-w-0 scroll-mt-4 rounded-xl border border-border-01 p-4 sm:p-5">
                  <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-2">
                    <h2 className="font-semibold text-text-05">{workspaceText("finding")}{" "}{finding.number} · {statusLabels[finding.status]}</h2>
                    <span className="rounded-full bg-background-neutral-02 px-2 py-1 text-xs text-text-05">
                      {latest ? actions[latest.action].past : finding.is_open ? "Awaiting decision" : "Aligned"}
                    </span>
                  </ResponsiveLayout>
                  <p className="mt-2 break-words text-sm text-text-05">{finding.explanation}</p>
                  {(finding.document_quote || finding.policy_quote) && (
                    <dl className="mt-3 grid gap-2 text-sm text-text-03 sm:grid-cols-2">
                      {finding.document_quote && <div><dt className="font-medium text-text-05">{workspaceText("documentExcerpt")}</dt><dd className="break-words">{finding.document_quote}</dd></div>}
                      {finding.policy_quote && <div><dt className="font-medium text-text-05">{workspaceText("policyExcerpt")}</dt><dd className="break-words">{finding.policy_quote}</dd></div>}
                    </dl>
                  )}
                  {finding.citation && (
                    <p className="mt-2 break-words text-sm text-text-03">{workspaceText("citation")}{" "}{finding.citation.number} · {external ? (
                        <a href={finding.citation.link!} target="_blank" rel="noreferrer" className={textLink}>{finding.citation.title}</a>
                      ) : (
                        <NavLink href={`/app?chatId=${data.chat_session_id}`} className={textLink}>{finding.citation.title}</NavLink>
                      )}
                    </p>
                  )}
                  {finding.decisions.length > 0 && (
                    <details className="mt-3 text-sm">
                      <summary className="cursor-pointer font-medium text-text-05">{workspaceText("decisionHistory")}{finding.decisions.length})</summary>
                      <ol className="mt-2 grid gap-2 border-l border-border-01 pl-3">
                        {finding.decisions.map((decision) => (
                          <li key={decision.id}>
                            <span className="font-medium text-text-05">{actions[decision.action].past}</span>
                            {" · "}
                            <time className="text-text-03" dateTime={decision.created_at}>{date.dateTime(new Date(decision.created_at), { dateStyle: "medium", timeStyle: "short" })}</time>
                            {decision.reason && <p className="whitespace-pre-wrap break-words text-text-03">{decision.reason}</p>}
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                  <DecisionForm reviewId={reviewId} finding={finding} onSaved={saved} onConflict={() => void mutate()} />
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
