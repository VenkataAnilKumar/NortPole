"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type { RoutePolicyView } from "@/lib/routePolicy/types";

export const ROUTE_POLICY_URL = "/api/route-policy";

/** The caller's view of the administrator's route policy for the default data class. */
export function useRoutePolicy() {
  return useSWR<RoutePolicyView>(ROUTE_POLICY_URL, errorHandlingFetcher, {
    revalidateOnFocus: true,
  });
}
