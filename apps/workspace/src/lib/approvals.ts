"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

interface ToolRow { id: number; name: string; approval: string | null; source: string; host: string | null }
interface Changes { pending: { own: boolean }[] }

/**
 * What is waiting for an administrator, from the queues the Approvals page shows. Only counts what the viewer
 * could act on: an administrator's own proposed change is not counted, and the server already leaves a person's own
 * sends out of the second-approver queue.
 */
export function useApprovalCounts() {
  const sends = useSWR<unknown[]>("/api/admin/actions/awaiting-second", errorHandlingFetcher, { refreshInterval: 30000 });
  const changes = useSWR<Changes>("/api/admin/changes", errorHandlingFetcher, { refreshInterval: 30000 });
  const requests = useSWR<{ pending: unknown[] }>("/api/admin/source-requests", errorHandlingFetcher, { refreshInterval: 30000 });
  const catalog = useSWR<{ tools: ToolRow[] }>("/api/admin/tool-catalog", errorHandlingFetcher);
  const tools = (catalog.data?.tools ?? []).filter((t) => t.approval !== null && t.approval !== "approved");
  const counts = {
    sends: sends.data?.length ?? 0,
    changes: (changes.data?.pending ?? []).filter((c) => !c.own).length,
    tools: tools.length,
    requests: requests.data?.pending.length ?? 0,
  };
  return {
    ...counts,
    total: counts.sends + counts.changes + counts.tools + counts.requests,
    tools_waiting: tools,
    loaded: sends.data !== undefined && changes.data !== undefined && catalog.data !== undefined && requests.data !== undefined,
  };
}
