import { titleCase } from "@/sections/sources/shared";

/** One integration as the catalog shows it to one person (GET /api/integrations). */
export interface IntegrationItem {
  id: string;
  name: string;
  description: string;
  kind: "connector" | "plugin";
  group: "horizontal" | "vertical";
  category: string;
  version: string;
  hosts: string[];
  data_classes: string[];
  needs_account: boolean;
  auth_mode: "none" | "oauth" | "api_key";
  has_writes: boolean;
  actions: { id: string; name: string; description: string; effect: "read" | "write" }[];
  skills: { name: string; description: string; content: string }[];
  state: "available" | "needs_approval" | "blocked" | "installed" | "connected";
  policy: string;
  installed_version: string | null;
  update_available: boolean;
}

export const CATALOG_URL = "/api/integrations";
export const REQUESTS_URL = "/api/sources/discover";

export const GROUP_LABEL: Record<string, string> = { horizontal: "Horizontal", vertical: "Vertical" };
export const KIND_LABEL: Record<string, string> = { connector: "Connector", plugin: "Plugin" };
const SPECIAL: Record<string, string> = { gtm: "GTM" };

export function categoryLabel(category: string): string {
  return SPECIAL[category] ?? titleCase(category);
}

/** Calls the integration routes and returns the new state, or throws an Error whose message is safe to show. */
export async function send(method: "POST" | "PUT" | "DELETE", url: string, body?: unknown): Promise<void> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : `The request failed (HTTP ${res.status}).`);
  }
}

export const secondary =
  "min-h-11 rounded-xl border border-border-02 px-4 text-sm font-semibold text-text-05 disabled:opacity-50";
export const primary =
  "min-h-11 rounded-xl bg-text-05 px-4 text-sm font-semibold text-background-neutral-00 disabled:opacity-50";
