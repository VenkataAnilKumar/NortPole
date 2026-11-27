"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { useRoutePolicy, ROUTE_POLICY_URL } from "@/lib/routePolicy/hooks";
import type { DataClass, RouteKind, RoutePolicyView } from "@/lib/routePolicy/types";

const KIND_LABEL: Record<RouteKind, string> = { local: "Local", private: "Private", cloud: "Cloud" };
const CLASS_LABEL: Record<DataClass, string> = {
  public: "Public",
  internal: "Internal",
  confidential: "Confidential",
  restricted: "Restricted",
};

interface Draft {
  defaultClass: DataClass;
  allowed: Record<DataClass, RouteKind[]>;
  kinds: Record<number, RouteKind>;
  redact: RouteKind[];
}

function toDraft(v: RoutePolicyView): Draft {
  const kinds: Record<number, RouteKind> = {};
  v.routes.forEach((r) => (kinds[r.provider_id] = r.kind));
  return { defaultClass: v.default_data_class, allowed: structuredClone(v.allowed), kinds, redact: [...(v.redact_route_kinds ?? [])] };
}

async function callJson(url: string, method: string, body: { default_data_class: string; allowed: Record<string, string[]>; route_kinds: Record<string, RouteKind>; redact_route_kinds: string[] } | { provider_id: number; data_class: string }) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* not json */
  }
  if (!res.ok) throw new Error(data?.detail || data?.message || `Request failed (${res.status})`);
  return data;
}

const AUDIT_URL = "/api/admin/route-policy/audit?limit=25";

interface AuditEvent {
  id: number;
  created_at: string;
  action: string;
  outcome: string;
  actor_email: string | null;
  summary: string;
}

const ACTION_LABEL: Record<string, string> = {
  "route_policy.change": "Policy changed",
  "route.blocked": "Request blocked",
};

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const select =
  "min-h-10 rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05";

export default function RoutePolicyPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data: policy, error } = useRoutePolicy();
  const { data: audit } = useSWR<AuditEvent[]>(AUDIT_URL, errorHandlingFetcher, { refreshInterval: 15000 });
  const { data: tokens } = useSWR<{ route_kind: string; model_name: string; calls: number; prompt_tokens: number; completion_tokens: number; estimated_cost_cents: number | null; unpriced_calls: number }[]>(
    "/api/admin/route-tokens?days=30",
    errorHandlingFetcher,
    { refreshInterval: 30000 }
  );
  const { data: usage } = useSWR<{ route_kind: string; model_name: string; data_class: string; purpose: string; requests: number }[]>(
    "/api/admin/route-usage?days=30",
    errorHandlingFetcher,
    { refreshInterval: 30000 }
  );
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [testProvider, setTestProvider] = useState<number | null>(null);
  const [testClass, setTestClass] = useState<DataClass>("confidential");
  const [testResult, setTestResult] = useState<{ allowed: boolean; kind: string; reason: string | null } | null>(null);

  useEffect(() => {
    if (policy) setDraft(toDraft(policy));
  }, [policy]);

  const dirty = useMemo(
    () => !!policy && !!draft && JSON.stringify(draft) !== JSON.stringify(toDraft(policy)),
    [policy, draft]
  );

  if (error) {
    return <div className="p-8 text-sm text-text-05">{workspaceText("couldNotLoadTheRoutePolicy")}</div>;
  }
  if (!policy || !draft) {
    return <div className="p-8 text-sm text-text-03">{workspaceText("loadingRoutePolicy")}</div>;
  }

  const toggle = (cls: DataClass, kind: RouteKind) =>
    setDraft((d) => {
      if (!d) return d;
      const has = d.allowed[cls].includes(kind);
      return {
        ...d,
        allowed: { ...d.allowed, [cls]: has ? d.allowed[cls].filter((k) => k !== kind) : [...d.allowed[cls], kind] },
      };
    });

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const route_kinds: Record<string, RouteKind> = {};
      Object.entries(draft.kinds).forEach(([id, k]) => (route_kinds[id] = k));
      const saved = await callJson("/api/admin/route-policy", "PUT", {
        default_data_class: draft.defaultClass,
        allowed: draft.allowed,
        route_kinds,
        redact_route_kinds: draft.redact,
      });
      await mutate(ROUTE_POLICY_URL);
      await mutate(AUDIT_URL);
      await mutate("/api/admin/changes");
      if (saved?.pending_approval) {
        setStatus({ ok: true, text: "Not applied yet: a second administrator has to approve this change. You can follow it on the Governance page." });
      } else {
        setStatus({ ok: true, text: "Policy saved. It applies to new requests; past runs keep the version they used." });
      }
    } catch (e) {
      setStatus({ ok: false, text: e instanceof Error ? e.message : "Could not save." });
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    const id = testProvider ?? policy.routes[0]?.provider_id;
    if (id == null) return;
    try {
      // Test against the saved policy; save first to test a change.
      const d = await callJson("/api/route-policy/check", "POST", { provider_id: id, data_class: testClass });
      setTestResult(d);
    } catch (e) {
      setTestResult({ allowed: false, kind: "unknown", reason: e instanceof Error ? e.message : "Test failed" });
    }
  };

  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-4xl flex-col gap-6 p-8" data-testid="route-policy-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("routePolicy")}</h1>
        <p className="text-sm text-text-03">{workspaceText("decideWhichModelRoutesMayProcessWhichDataA")}{policy.version}.
        </p>
      </header>

      <section aria-labelledby="rp-routes" className={card}>
        <h2 id="rp-routes" className="mb-1 text-base font-semibold text-text-05">{workspaceText("routes")}</h2>
        <p className="mb-4 text-sm text-text-03">{workspaceText("setTheTypeOfEachRegisteredModelProviderA")}</p>
        {policy.routes.length === 0 ? (
          <p className="text-sm text-text-03">{workspaceText("noModelProvidersAreRegisteredYet")}</p>
        ) : (
          <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={workspaceText("modelRoutes")} tabIndex={0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-03">
                <th className="py-2 pr-3 font-medium">{workspaceText("provider")}</th>
                <th className="py-2 pr-3 font-medium">{workspaceText("models")}</th>
                <th className="py-2 font-medium">{workspaceText("routeType")}</th>
              </tr>
            </thead>
            <tbody>
              {policy.routes.map((r) => (
                <tr key={r.provider_id} className="border-t border-border-01">
                  <td className="py-3 pr-3 font-medium text-text-05">{r.name ?? r.provider}</td>
                  <td className="py-3 pr-3 text-text-03">{r.model_names.join(", ") || "None visible"}</td>
                  <td className="py-3">
                    <label className="sr-only" htmlFor={`kind-${r.provider_id}`}>{workspaceText("routeTypeFor")}{" "}{r.name ?? r.provider}</label>
                    <NativeSelect
                      id={`kind-${r.provider_id}`}
                      className={select}
                      value={draft.kinds[r.provider_id]}
                      onChange={(e) =>
                        setDraft((d) => (d ? { ...d, kinds: { ...d.kinds, [r.provider_id]: e.target.value as RouteKind } } : d))
                      }
                    >
                      {policy.route_kinds.map((k) => (
                        <option key={k} value={k}>{KIND_LABEL[k]}</option>
                      ))}
                    </NativeSelect>
                    {!r.kind_assigned && <span className="ml-2 text-xs text-text-03">{workspaceText("notSetYet")}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>

      <section aria-labelledby="rp-redact" className={card} data-testid="redaction-settings">
        <h2 id="rp-redact" className="mb-1 text-base font-semibold text-text-05">{workspaceText("sensitiveDataRedaction")}</h2>
        <p className="mb-3 text-sm text-text-03">{workspaceText("beforeARequestIsSentToTheTickedRoute")}</p>
        <ResponsiveLayout display="flex" className="flex-wrap gap-4">
          {policy.route_kinds.map((k) => (
            <label key={k} className="inline-flex min-h-10 cursor-pointer items-center gap-2 text-sm text-text-05">
              <NativeInput
                type="checkbox"
                checked={draft.redact.includes(k)}
                onChange={() =>
                  setDraft((d) => (d ? { ...d, redact: d.redact.includes(k) ? d.redact.filter((x) => x !== k) : [...d.redact, k] } : d))
                }
              />
              {KIND_LABEL[k]}
            </label>
          ))}
        </ResponsiveLayout>
        <p className="mt-2 text-xs text-text-03">{workspaceText("savedWithTheRestOfThePolicyBelow")}</p>
      </section>

      <section aria-labelledby="rp-matrix" className={card}>
        <h2 id="rp-matrix" className="mb-1 text-base font-semibold text-text-05">{workspaceText("allowedRoutesByDataClass")}</h2>
        <p className="mb-4 text-sm text-text-03">{workspaceText("tickTheRouteTypesThatMayProcessEachClass")}</p>
        <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={workspaceText("allowedRoutesByDataClass")} tabIndex={0}>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-03">
              <th className="py-2 pr-3 font-medium">{workspaceText("dataClass")}</th>
              {policy.route_kinds.map((k) => (
                <th key={k} className="py-2 pr-3 text-center font-medium">{KIND_LABEL[k]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {policy.data_classes.map((cls) => (
              <tr key={cls} className="border-t border-border-01">
                <th scope="row" className="py-3 pr-3 text-left font-medium text-text-05">{CLASS_LABEL[cls]}</th>
                {policy.route_kinds.map((k) => {
                  const on = draft.allowed[cls].includes(k);
                  return (
                    <td key={k} className="py-3 pr-3 text-center">
                      <label className="inline-flex min-h-10 min-w-10 cursor-pointer items-center justify-center">
                        <NativeInput
                          type="checkbox"
                          className="h-5 w-5"
                          checked={on}
                          onChange={() => toggle(cls, k)}
                          aria-label={`${CLASS_LABEL[cls]} data on ${KIND_LABEL[k]} routes`}
                        />
                        <span className="sr-only">{on ? "Allowed" : "Blocked"}</span>
                      </label>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <ResponsiveLayout display="flex" className="mt-4 flex-wrap items-center gap-3">
          <label htmlFor="rp-default" className="text-sm font-medium text-text-05">{workspaceText("thisWorkspaceSDataClass")}</label>
          <NativeSelect
            id="rp-default"
            className={select}
            value={draft.defaultClass}
            onChange={(e) => setDraft((d) => (d ? { ...d, defaultClass: e.target.value as DataClass } : d))}
          >
            {policy.data_classes.map((c) => (
              <option key={c} value={c}>{CLASS_LABEL[c]}</option>
            ))}
          </NativeSelect>
          <span className="text-xs text-text-03">{workspaceText("usedForEveryTaskUntilPerTaskClassificationExists")}</span>
        </ResponsiveLayout>
      </section>

      <ResponsiveLayout display="flex" className="flex-wrap items-center gap-3">
        <ActionButton
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="min-h-11 rounded-xl bg-text-05 px-5 text-sm font-semibold text-background-neutral-00 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save policy"}
        </ActionButton>
        {dirty && (
          <ActionButton
            type="button"
            onClick={() => setDraft(toDraft(policy))}
            className="min-h-11 rounded-xl border border-border-02 px-5 text-sm font-semibold text-text-05"
          >{workspaceText("discardChanges")}</ActionButton>
        )}
        {status && (
          <p role="status" className={`text-sm ${status.ok ? "text-status-success-05" : "text-status-text-error-05"}`}>
            {status.text}
          </p>
        )}
      </ResponsiveLayout>

      <section aria-labelledby="rp-test" className={card}>
        <h2 id="rp-test" className="mb-1 text-base font-semibold text-text-05">{workspaceText("testARequestAgainstTheSavedPolicy")}</h2>
        <ResponsiveLayout display="flex" className="mt-3 flex-wrap items-end gap-3">
          <ResponsiveLayout display="flex" className="flex-col gap-1">
            <label htmlFor="rp-test-class" className="text-xs font-medium text-text-03">{workspaceText("dataClass")}</label>
            <NativeSelect id="rp-test-class" className={select} value={testClass} onChange={(e) => setTestClass(e.target.value as DataClass)}>
              {policy.data_classes.map((c) => (
                <option key={c} value={c}>{CLASS_LABEL[c]}</option>
              ))}
            </NativeSelect>
          </ResponsiveLayout>
          <ResponsiveLayout display="flex" className="flex-col gap-1">
            <label htmlFor="rp-test-route" className="text-xs font-medium text-text-03">{workspaceText("requestedRoute")}</label>
            <NativeSelect
              id="rp-test-route"
              className={select}
              value={testProvider ?? policy.routes[0]?.provider_id ?? ""}
              onChange={(e) => setTestProvider(Number(e.target.value))}
            >
              {policy.routes.map((r) => (
                <option key={r.provider_id} value={r.provider_id}>{r.name ?? r.provider}</option>
              ))}
            </NativeSelect>
          </ResponsiveLayout>
          <ActionButton type="button" onClick={runTest} className="min-h-10 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05">{workspaceText("runTest")}</ActionButton>
        </ResponsiveLayout>
        {testResult && (
          <p
            role="status"
            className={`mt-4 rounded-xl px-4 py-3 text-sm ${testResult.allowed ? "bg-status-success-01 text-status-success-05" : "bg-status-error-01 text-status-text-error-05"}`}
          >
            {testResult.allowed
              ? `Allowed: ${testResult.kind} routes may process this data class.`
              : `POLICY_BLOCKED before send. ${testResult.reason ?? ""} No content would be transmitted.`}
          </p>
        )}
      </section>

      <section aria-labelledby="rp-usage" className={card} data-testid="route-usage">
        <h2 id="rp-usage" className="text-base font-semibold text-text-05">{workspaceText("whereRequestsRanLast30Days")}</h2>
        <p className="mt-1 text-sm text-text-03">{workspaceText("allowedModelRequestsCountedByRouteModelDataClass")}</p>
        {!usage || usage.length === 0 ? (
          <p className="mt-3 text-sm text-text-03">{workspaceText("noModelRequestsHaveBeenCountedYet")}</p>
        ) : (
          <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={workspaceText("requestsByRoute")} tabIndex={0}>
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="text-text-03">
                <th className="py-2 pr-3 font-medium">{workspaceText("route_499952")}</th>
                <th className="py-2 pr-3 font-medium">{workspaceText("model")}</th>
                <th className="py-2 pr-3 font-medium">{workspaceText("dataClass")}</th>
                <th className="py-2 pr-3 font-medium">{workspaceText("purpose")}</th>
                <th className="py-2 text-right font-medium">{workspaceText("requests")}</th>
              </tr>
            </thead>
            <tbody>
              {usage.map((u) => (
                <tr key={`${u.route_kind}-${u.model_name}-${u.data_class}-${u.purpose}`} className="border-t border-border-01">
                  <td className="py-2 pr-3 text-text-05">{u.route_kind}</td>
                  <td className="py-2 pr-3 text-text-05">{u.model_name}</td>
                  <td className="py-2 pr-3 text-text-05">{u.data_class}</td>
                  <td className="py-2 pr-3 text-text-05">{u.purpose.replace("_", " ")}</td>
                  <td className="py-2 text-right text-text-05">{u.requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>

      <section aria-labelledby="rp-tokens" className={card} data-testid="route-tokens">
        <h2 id="rp-tokens" className="text-base font-semibold text-text-05">{workspaceText("tokensAndEstimatedCostLast30Days")}</h2>
        <p className="mt-1 text-sm text-text-03">{workspaceText("tokensTheModelsReportedUsingByRouteAndModel")}</p>
        {!tokens || tokens.length === 0 ? (
          <p className="mt-3 text-sm text-text-03">{workspaceText("noModelCallsWithTokenCountsHaveBeenRecorded")}</p>
        ) : (
          <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={workspaceText("tokensAndCostByRoute")} tabIndex={0}>
            <table className="mt-3 w-full text-left text-sm">
              <thead>
                <tr className="text-text-03">
                  <th scope="col" className="py-2 pr-3 font-medium">{workspaceText("route_499952")}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{workspaceText("model")}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{workspaceText("calls")}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{workspaceText("promptTokens")}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{workspaceText("answerTokens")}</th>
                  <th scope="col" className="py-2 text-right font-medium">{workspaceText("estimatedCost")}</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => (
                  <tr key={`${t.route_kind}-${t.model_name}`} className="border-t border-border-01">
                    <td className="py-2 pr-3 text-text-05">{t.route_kind}</td>
                    <td className="py-2 pr-3 text-text-05">{t.model_name}</td>
                    <td className="py-2 pr-3 text-right text-text-05">{t.calls.toLocaleString()}</td>
                    <td className="py-2 pr-3 text-right text-text-05">{t.prompt_tokens.toLocaleString()}</td>
                    <td className="py-2 pr-3 text-right text-text-05">{t.completion_tokens.toLocaleString()}</td>
                    <td className="py-2 text-right text-text-05">
                      {t.estimated_cost_cents === null
                        ? "not priced"
                        : `$${(t.estimated_cost_cents / 100).toFixed(t.estimated_cost_cents === 0 ? 2 : 4)}`}
                      {t.estimated_cost_cents !== null && t.unpriced_calls > 0 && (
                        <span className="block text-xs text-text-03">{t.unpriced_calls} of {t.calls}{" "}{workspaceText("callsNotPriced")}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="rp-audit" className={card}>
        <h2 id="rp-audit" className="mb-1 text-base font-semibold text-text-05">{workspaceText("recentActivity")}</h2>
        <p className="mb-3 text-sm text-text-03">{workspaceText("policyChangesAndRequestsTheServerRefusedEntriesHold")}</p>
        {!audit ? (
          <p className="text-sm text-text-03">{workspaceText("loading")}</p>
        ) : audit.length === 0 ? (
          <p className="text-sm text-text-03">{workspaceText("nothingRecordedYet")}</p>
        ) : (
          <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" role="region" aria-label={workspaceText("recentActivity")} tabIndex={0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-03">
                <th className="py-2 pr-3 font-medium">{workspaceText("when")}</th>
                <th className="py-2 pr-3 font-medium">{workspaceText("event")}</th>
                <th className="py-2 pr-3 font-medium">{workspaceText("who")}</th>
                <th className="py-2 font-medium">{workspaceText("details")}</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((e) => (
                <tr key={e.id} className="border-t border-border-01 align-top">
                  <td className="whitespace-nowrap py-2 pr-3 text-text-03">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-3">
                    <span
                      className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${e.outcome === "denied" ? "bg-status-error-01 text-status-text-error-05" : "bg-background-neutral-02 text-text-05"}`}
                    >
                      {ACTION_LABEL[e.action] ?? e.action}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-text-05">{e.actor_email ?? "System"}</td>
                  <td className="py-2 text-text-05">{e.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>
    </ResponsiveLayout>
  );
}
