"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";

export interface OwnTask { id: string; title: string; state: string; updated_at: string }

/**
 * The person's own drafts that wait for them: a plan to accept (To approve) or a draft to review (To review). Only
 * their own drafts are listed, so the titles shown are their own.
 */
export function useOwnWork(refreshInterval = 60_000) {
  const { data } = useSWR<OwnTask[]>("/api/tasks", errorHandlingFetcher, { refreshInterval, shouldRetryOnError: false });
  const tasks = Array.isArray(data) ? data : [];
  return {
    plans: tasks.filter((t) => t.state === "plan_review"),
    drafts: tasks.filter((t) => t.state === "draft_ready"),
    loaded: data !== undefined,
  };
}
