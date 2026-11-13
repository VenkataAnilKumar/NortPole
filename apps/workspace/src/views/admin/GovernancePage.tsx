"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import AdminApprovals from "@/views/admin/AdminApprovals";

interface RoutePolicy { default_data_class: string; redact_route_kinds?: string[]; allowed: Record<string, string[]> }
interface Extensions { personal_skills: string; mcp_allowlist_enabled: boolean; mcp_allowed_hosts: string[] }
interface Retention { audit_days: number | null; usage_days: number | null; legal_hold: boolean; hold_reason: string; last_prune_at: string | null }
interface Target { name: string; tier?: string; enabled: boolean }

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const TIER: Record<string, string> = { act_with_approval: "act with approval", draft_only: "draft only", read_only: "read only" };

function Row({ title, where, href, children }: { title: string; where: string; href: string; children: React.ReactNode }) {
  return (
    <li className={card} data-testid="gov-row">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-text-05">{title}</h2>
          <p className="mt-1 text-sm text-text-05">{children}</p>
        </div>
        <a href={href} className="min-h-11 rounded-xl border border-border-02 px-4 py-2.5 text-sm font-semibold text-text-05">
          Change in {where}
        </a>
      </div>
    </li>
  );
}

/** Where each governance control lives and what it is set to now. Read-only; each link opens the page that changes it. */
export default function GovernancePage() {
  const { data: rp } = useSWR<RoutePolicy>("/api/route-policy", errorHandlingFetcher);
  const { data: ext } = useSWR<Extensions>("/api/admin/extensions", errorHandlingFetcher);
  const { data: ret } = useSWR<Retention>("/api/admin/retention", errorHandlingFetcher);
  const { data: targets } = useSWR<{ name: string; tier?: string; enabled: boolean }[]>("/api/admin/action-targets", errorHandlingFetcher);

  const tiers = (targets ?? []).reduce<Record<string, number>>((m, t: Target) => ({ ...m, [t.tier ?? "act_with_approval"]: (m[t.tier ?? "act_with_approval"] ?? 0) + 1 }), {});
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 p-4 sm:p-8" data-testid="governance-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">Governance</h1>
        <p className="mt-1 text-sm text-text-03">
          The controls that decide what may reach a model, what may be sent out, and what is kept. This page only shows their current setting; each link opens the page where it is changed.
        </p>
      </div>
      <ul className="flex flex-col gap-4">
        <Row title="Model routes and data classes" where="Route policy" href="/admin/route-policy">
          {rp ? <>The workspace treats its data as <b>{rp.default_data_class}</b>. Cloud routes may process: {Object.entries(rp.allowed).filter(([, k]) => k.includes("cloud")).map(([c]) => c).join(", ") || "no data class"}.</> : "Loading…"}
        </Row>
        <Row title="Sensitive-data redaction" where="Route policy" href="/admin/route-policy">
          {rp ? <>Listed patterns (emails, phone and card numbers, keys and similar) are replaced before sending to: <b>{(rp.redact_route_kinds ?? []).join(", ") || "no route type"}</b>.</> : "Loading…"}
        </Row>
        <Row title="Send destinations and how far they may go" where="Send destinations" href="/admin/action-targets">
          {targets ? <>{targets.length} destination{targets.length === 1 ? "" : "s"}: {Object.entries(tiers).map(([t, n]) => `${n} ${TIER[t] ?? t}`).join(", ") || "none registered"}.</> : "Loading…"}
        </Row>
        <Row title="What people may add" where="Inventory" href="/admin/inventory">
          {ext ? <>Personal skills: <b>{ext.personal_skills === "off" ? "off" : "self-serve"}</b>. MCP host allowlist: <b>{ext.mcp_allowlist_enabled ? `on (${ext.mcp_allowed_hosts.length} host${ext.mcp_allowed_hosts.length === 1 ? "" : "s"})` : "off"}</b>.</> : "Loading…"}
        </Row>
        <Row title="Retention, legal hold and audit export" where="Audit log" href="/admin/audit">
          {ret ? <>Audit events kept {ret.audit_days === null ? "forever" : `${ret.audit_days} days`}; usage counts {ret.usage_days === null ? "forever" : `${ret.usage_days} days`}. Legal hold: <b>{ret.legal_hold ? `on (${ret.hold_reason})` : "off"}</b>. The periods are placeholders until you set them.</> : "Loading…"}
        </Row>
        <Row title="Signed packs and who signs them" where="Packs" href="/admin/packs">
          Packs install only if signed by a trusted signer, and run only on models they passed evaluation on.
        </Row>
        <Row title="Who did what" where="Audit log" href="/admin/audit">
          Refusals, policy changes, approvals, sends and exports are written to the audit log.
        </Row>
      </ul>
      <AdminApprovals />
    </div>
  );
}
