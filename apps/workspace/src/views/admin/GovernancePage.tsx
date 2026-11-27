"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { NavLink } from "@opal/navigation";
import type { Route } from "next";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface RoutePolicy { default_data_class: string; redact_route_kinds?: string[]; allowed: Record<string, string[]> }
interface Extensions { personal_skills: string; mcp_allowlist_enabled: boolean; mcp_allowed_hosts: string[] }
interface Retention { audit_days: number | null; usage_days: number | null; legal_hold: boolean; hold_reason: string; last_prune_at: string | null }
interface Target { name: string; tier?: string; enabled: boolean }

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const TIER: Record<string, string> = { act_with_approval: "act with approval", draft_only: "draft only", read_only: "read only" };

function Row({ title, where, destination, children }: { title: string; where: string; destination: Route; children: React.ReactNode }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  return (
    <li className={card} data-testid="gov-row">
      <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-text-05">{title}</h2>
          <p className="mt-1 text-sm text-text-05">{children}</p>
        </div>
        <NavLink href={destination} className="min-h-11 rounded-xl border border-border-02 px-4 py-2.5 text-sm font-semibold text-text-05">{workspaceText("changeIn")}{" "}{where}
        </NavLink>
      </ResponsiveLayout>
    </li>
  );
}

/** Where each governance control lives and what it is set to now. Read-only; each link opens the page that changes it. */
export default function GovernancePage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data: rp } = useSWR<RoutePolicy>("/api/route-policy", errorHandlingFetcher);
  const { data: ext } = useSWR<Extensions>("/api/admin/extensions", errorHandlingFetcher);
  const { data: ret } = useSWR<Retention>("/api/admin/retention", errorHandlingFetcher);
  const { data: targets } = useSWR<{ name: string; tier?: string; enabled: boolean }[]>("/api/admin/action-targets", errorHandlingFetcher);

  const tiers = (targets ?? []).reduce<Record<string, number>>((m, t: Target) => ({ ...m, [t.tier ?? "act_with_approval"]: (m[t.tier ?? "act_with_approval"] ?? 0) + 1 }), {});
  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-4xl flex-col gap-4 p-4 sm:p-8" data-testid="governance-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("governance")}</h1>
        <p className="mt-1 text-sm text-text-03">{workspaceText("theControlsThatDecideWhatMayReachAModel")}</p>
      </div>
      <ul className="flex flex-col gap-4">
        <Row title={workspaceText("modelRoutesAndDataClasses")} where="Route policy" destination="/admin/route-policy">
          {rp ? <>{workspaceText("theWorkspaceTreatsItsDataAs")}{" "}<b>{rp.default_data_class}</b>{workspaceText("cloudRoutesMayProcess")}{" "}{Object.entries(rp.allowed).filter(([, k]) => k.includes("cloud")).map(([c]) => c).join(", ") || "no data class"}.</> : "Loading…"}
        </Row>
        <Row title={workspaceText("sensitiveDataRedaction")} where="Route policy" destination="/admin/route-policy">
          {rp ? <>{workspaceText("listedPatternsEmailsPhoneAndCardNumbersKeysAnd")}{" "}<b>{(rp.redact_route_kinds ?? []).join(", ") || "no route type"}</b>.</> : "Loading…"}
        </Row>
        <Row title={workspaceText("sendDestinationsAndHowFarTheyMayGo")} where="Send destinations" destination="/admin/action-targets">
          {targets ? <>{targets.length} destination{targets.length === 1 ? "" : "s"}: {Object.entries(tiers).map(([t, n]) => `${n} ${TIER[t] ?? t}`).join(", ") || "none registered"}.</> : "Loading…"}
        </Row>
        <Row title={workspaceText("whatPeopleMayAdd")} where="Inventory" destination="/admin/inventory">
          {ext ? <>{workspaceText("personalSkills")}{" "}<b>{ext.personal_skills === "off" ? "off" : "self-serve"}</b>{workspaceText("mcpHostAllowlist")}{" "}<b>{ext.mcp_allowlist_enabled ? `on (${ext.mcp_allowed_hosts.length} host${ext.mcp_allowed_hosts.length === 1 ? "" : "s"})` : "off"}</b>.</> : "Loading…"}
        </Row>
        <Row title={workspaceText("retentionLegalHoldAndAuditExport")} where="Audit log" destination="/admin/audit">
          {ret ? <>{workspaceText("auditEventsKept")}{" "}{ret.audit_days === null ? "forever" : `${ret.audit_days} days`}{workspaceText("usageCounts")}{" "}{ret.usage_days === null ? "forever" : `${ret.usage_days} days`}{workspaceText("legalHold")}{" "}<b>{ret.legal_hold ? `on (${ret.hold_reason})` : "off"}</b>{workspaceText("thePeriodsArePlaceholdersUntilYouSetThem")}</> : "Loading…"}
        </Row>
        <Row title={workspaceText("signedPacksAndWhoSignsThem")} where="Packs" destination="/admin/packs">{workspaceText("packsInstallOnlyIfSignedByATrustedSigner")}</Row>
        <Row title={workspaceText("changesThatNeedASecondAdministrator")} where="Approvals" destination="/admin/approvals">{workspaceText("whichKindsOfChangeNeedASecondAdministratorAnd")}</Row>
        <Row title={workspaceText("whoDidWhat")} where="Audit log" destination="/admin/audit">{workspaceText("refusalsPolicyChangesApprovalsSendsAndExportsAreWritten")}</Row>
      </ul>
    </ResponsiveLayout>
  );
}
