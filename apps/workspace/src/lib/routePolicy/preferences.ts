import type { RouteKind } from "@/lib/routePolicy/types";

export type DefaultRoute = "auto" | RouteKind;

const KEY = "evolvxsi.defaultRoute";

/**
 * The user's preferred route for new tasks. It is a preference only: the server
 * checks the administrator's policy on every request, and a preferred route the
 * policy blocks is ignored. Stored in this browser for now; syncing it across
 * devices needs a server-side user preference.
 */
export function getDefaultRoute(): DefaultRoute {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === "local" || v === "private" || v === "cloud") return v;
  } catch {
    /* storage unavailable */
  }
  return "auto";
}

export function setDefaultRoute(route: DefaultRoute): void {
  try {
    window.localStorage.setItem(KEY, route);
  } catch {
    /* storage unavailable */
  }
}
