"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NavLink } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useApprovalCounts } from "@/lib/approvals";
import AdminApprovals from "@/views/admin/AdminApprovals";
import SecondApproverQueue from "@/views/admin/SecondApproverQueue";
import SourceRequestsQueue from "@/views/admin/SourceRequestsQueue";

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";
const STATUS: Record<string, string> = {
  "not approved": "Not approved yet",
  "changed since approved": "Changed since it was approved",
  "changed on its server": "Changed on its server",
};

/**
 * Everything waiting for an administrator, in one place: sends that need a second approver, requests from Discover, administrator changes
 * that need a second administrator, and outside tools whose definition needs approving. Each item is decided where
 * it is shown, except tool definitions, which are reviewed on the Tools page next to what the model is told.
 */
export default function ApprovalsPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const c = useApprovalCounts();
  const summary = !c.loaded
    ? "Loading…"
    : c.total === 0
      ? "Nothing is waiting."
      : [
          c.sends && `${c.sends} ${c.sends === 1 ? "send" : "sends"}`,
          c.changes && `${c.changes} administrator ${c.changes === 1 ? "change" : "changes"}`,
          c.tools && `${c.tools} tool ${c.tools === 1 ? "definition" : "definitions"}`,
          c.requests && `${c.requests} ${c.requests === 1 ? "request" : "requests"} from people`,
        ].filter(Boolean).join(", ") + " waiting.";

  return (
    <ResponsiveLayout display="flex" className="mx-auto w-full max-w-4xl flex-col gap-5 p-4 sm:p-8" data-testid="approvals-page">
      <div>
        <h1 className="text-2xl font-semibold text-text-05">{workspaceText("approvals")}</h1>
        <p className="mt-1 text-sm text-text-03">{workspaceText("everythingWaitingForAnAdministratorToDecide")}</p>
        <p role="status" className="mt-2 text-sm font-medium text-text-05" data-testid="approvals-summary">{summary}</p>
      </div>

      <SecondApproverQueue />

      <SourceRequestsQueue />

      <AdminApprovals />

      <section className={card} aria-labelledby="tool-defs" data-testid="tool-definitions">
        <h2 id="tool-defs" className="text-base font-semibold text-text-05">{workspaceText("outsideToolDefinitions")}</h2>
        <p className="mt-1 text-sm text-text-03">{workspaceText("anOutsideToolMcpOrOpenapiIsNeverOffered")}</p>
        {c.tools_waiting.length === 0 ? (
          <p className="mt-3 text-sm text-text-03">{workspaceText("nothingIsWaiting")}</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {c.tools_waiting.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border-01 px-3 py-2 text-sm" data-testid="tool-definition">
                <span className="min-w-0 text-text-05">
                  <span className="font-medium">{t.name}</span>
                  <span className="block text-xs text-text-03">{t.source}{t.host ? ` (${t.host})` : ""} · {STATUS[t.approval ?? ""] ?? t.approval}</span>
                </span>
                <NavLink href="/admin/tool-catalog" className="inline-flex min-h-11 items-center rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05">{workspaceText("reviewOnTheToolsPage")}</NavLink>
              </li>
            ))}
          </ul>
        )}
      </section>
    </ResponsiveLayout>
  );
}
