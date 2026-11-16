import { IconFunctionComponent } from "@opal/types";
import {
  ADMIN_ROUTES,
  AdminRouteEntry,
  FeatureFlags,
} from "@/lib/admin-routes";
import { hasPermission } from "@/lib/permissions/utils";
import { Settings } from "@/lib/settings/types";
import { Tier } from "@/lib/tiers/types";
import { tierAtLeast } from "@/lib/tiers/utils";

export type { FeatureFlags } from "@/lib/admin-routes";

/**
 * Stable id of one sidebar entry. The visible label is the
 * `sidebar.adminNav.items.<id>.label` message, resolved in `AdminSidebar`.
 */
export type AdminNavItemId =
  | "languageModels"
  | "routePolicy"
  | "accessGroups"
  | "actionTargets"
  | "auditLog"
  | "packsAdmin"
  | "inventory"
  | "toolCatalog"
  | "integrations"
  | "studio"
  | "governance"
  | "overview"
  | "quality"
  | "approvals"
  | "scheduling"
  | "webSearch"
  | "imageGeneration"
  | "voice"
  | "decisionModels"
  | "codeInterpreter"
  | "chatPreferences"
  | "llmGateway"
  | "craftAccess"
  | "craftApps"
  | "craftPreferences"
  | "skills"
  | "customAnalytics"
  | "agents"
  | "plugins"
  | "mcpActions"
  | "openapiActions"
  | "indexingStatus"
  | "connectors"
  | "documentSets"
  | "indexSettings"
  | "serviceAccounts"
  | "slackIntegration"
  | "discordIntegration"
  | "hookExtensions"
  | "users"
  | "groups"
  | "scim"
  | "plansAndBilling"
  | "appearanceAndTheming"
  | "securityAndHardening"
  | "ssoProviders"
  | "usage"
  | "spendingLimits"
  | "analytics"
  | "queryHistory"
  | "tracing"
  | "exportLogs"
  | "upgradePlan";

/**
 * Stable id of one sidebar section heading. The visible label is the
 * `sidebar.adminNav.sections.<id>.label` message.
 */
export type AdminNavSectionId =
  | "overview"
  | "approvals"
  | "governance"
  | "people"
  | "models"
  | "agentsAndTools"
  | "craft"
  | "knowledge"
  | "quality"
  | "platform";

/**
 * Sidebar id per admin route. `null` marks a route that never renders in the
 * sidebar, so a new route cannot silently arrive without a label.
 */
export const NAV_ITEM_IDS: Record<
  keyof typeof ADMIN_ROUTES,
  AdminNavItemId | null
> = {
  LLM_MODELS: "languageModels",
  ROUTE_POLICY: "routePolicy",
  ACCESS_GROUPS: "accessGroups",
  ACTION_TARGETS: "actionTargets",
  AUDIT_LOG: "auditLog",
  PACKS: "packsAdmin",
  STUDIO: "studio",
  INVENTORY: "inventory",
  TOOL_CATALOG: "toolCatalog",
  INTEGRATIONS: "integrations",
  GOVERNANCE: "governance",
  OVERVIEW: "overview",
  QUALITY: "quality",
  APPROVALS: "approvals",
  SCHEDULING: "scheduling",
  DECISION_MODELS: "decisionModels",
  WEB_SEARCH: "webSearch",
  IMAGE_GENERATION: "imageGeneration",
  VOICE: "voice",
  CODE_INTERPRETER: "codeInterpreter",
  CHAT_PREFERENCES: "chatPreferences",
  LLM_GATEWAY: "llmGateway",
  CRAFT_ACCESS: "craftAccess",
  CRAFT_APPS: null,
  CRAFT_PREFERENCES: "craftPreferences",
  SKILLS: "skills",
  CUSTOM_ANALYTICS: "customAnalytics",
  AGENTS: "agents",
  PLUGINS: "plugins",
  PLUGINS_EXTERNAL_APP: null,
  MCP_ACTIONS: null,
  OPENAPI_ACTIONS: null,
  INDEXING_STATUS: "indexingStatus",
  CONNECTORS: "connectors",
  DOCUMENT_SETS: "documentSets",
  DOCUMENT_EXPLORER: null,
  DOCUMENT_FEEDBACK: null,
  INDEX_SETTINGS: "indexSettings",
  DOCUMENT_PROCESSING: null,
  API_KEYS: "serviceAccounts",
  SLACK_BOTS: "slackIntegration",
  DISCORD_BOTS: "discordIntegration",
  HOOKS: "hookExtensions",
  USERS: "users",
  GROUPS: "groups",
  SCIM: "scim",
  OAUTH_TEST: null,
  BILLING: "plansAndBilling",
  THEME: "appearanceAndTheming",
  SECURITY_HARDENING: "securityAndHardening",
  SSO_PROVIDERS: "ssoProviders",
  USAGE: "usage",
  SPENDING_LIMITS: "spendingLimits",
  WORKSPACE_ANALYTICS: "analytics",
  QUERY_HISTORY: "queryHistory",
  TRACING: "tracing",
  EXPORT_LOGS: "exportLogs",
  STANDARD_ANSWERS: null,
  DOCUMENTS: null,
  PERFORMANCE: null,
};

/** Title id under `sidebar.adminNav.hiddenRoutes` for pages off the sidebar. */
export type AdminHiddenRouteId =
  | "documentExplorer"
  | "documentFeedback"
  | "documentProcessing"
  | "oauthTest"
  | "standardAnswers";

const HIDDEN_ROUTE_IDS: Partial<
  Record<keyof typeof ADMIN_ROUTES, AdminHiddenRouteId>
> = {
  DOCUMENT_EXPLORER: "documentExplorer",
  DOCUMENT_FEEDBACK: "documentFeedback",
  DOCUMENT_PROCESSING: "documentProcessing",
  OAUTH_TEST: "oauthTest",
  STANDARD_ANSWERS: "standardAnswers",
};

const ROUTE_KEYS = Object.keys(ADMIN_ROUTES) as (keyof typeof ADMIN_ROUTES)[];

const NAV_ID_BY_PATH: Record<string, AdminNavItemId | null> =
  Object.fromEntries(
    ROUTE_KEYS.map((key) => [ADMIN_ROUTES[key].path, NAV_ITEM_IDS[key]])
  );

const HIDDEN_ID_BY_PATH: Record<string, AdminHiddenRouteId | undefined> =
  Object.fromEntries(
    ROUTE_KEYS.map((key) => [ADMIN_ROUTES[key].path, HIDDEN_ROUTE_IDS[key]])
  );

/** Nav id for a route, for server components that resolve labels themselves. */
export function getAdminNavId(route: AdminRouteEntry): AdminNavItemId | null {
  return NAV_ID_BY_PATH[route.path] ?? null;
}

/** Hidden-route title id for a route outside the sidebar, if it has one. */
export function getAdminHiddenRouteId(
  route: AdminRouteEntry
): AdminHiddenRouteId | null {
  return HIDDEN_ID_BY_PATH[route.path] ?? null;
}

/** Section heading id per `AdminRouteEntry.section` value. */
const NAV_SECTION_IDS: readonly (readonly [
  section: string,
  id: AdminNavSectionId,
])[] = [
  // Sidebar order (redesign R2): health, what is waiting, then what people use (knowledge, agents and tools), the
  // controls, who, models, quality, and the platform settings that are set once.
  ["Overview", "overview"],
  ["Approvals", "approvals"],
  ["Knowledge", "knowledge"],
  ["Agents & tools", "agentsAndTools"],
  ["Craft", "craft"],
  ["Governance", "governance"],
  ["People", "people"],
  ["Models", "models"],
  ["Quality", "quality"],
  ["Platform", "platform"],
];

/** Sections whose heading shows a Beta tag. */
export const BETA_SECTION_IDS: ReadonlySet<AdminNavSectionId> = new Set([
  "craft",
]);

/** `null` for the unlabeled (default) section. */
function sectionIdFor(section: string): AdminNavSectionId | null {
  return NAV_SECTION_IDS.find(([label]) => label === section)?.[1] ?? null;
}

/**
 * Inherited screens with no use in the pilot. They stay reachable by address (and keep their titles) but are not in
 * the sidebar: Discord bot, SCIM provisioning, hook extensions, and plans and billing.
 */
const HIDDEN_FOR_PILOT: ReadonlySet<keyof typeof ADMIN_ROUTES> = new Set([
  "DISCORD_BOTS",
  "SCIM",
  "HOOKS",
  "BILLING",
]);

export interface SidebarItemEntry {
  /** `null` places the entry in the unlabeled (default) section. */
  sectionId: AdminNavSectionId | null;
  nameId: AdminNavItemId;
  icon: IconFunctionComponent;
  link: string;
  error?: boolean;
  disabled?: boolean;
  requiredTier?: Tier | null;
  beta?: boolean;
}

export function buildItems(
  permissions: string[],
  flags: FeatureFlags,
  settings: Settings | null
): SidebarItemEntry[] {
  const userCanAccess = (perm: string) => hasPermission(permissions, perm);
  const items: SidebarItemEntry[] = [];

  // Safety: ADMIN_ROUTES satisfies Record<string, AdminRouteEntry>, so every
  // entry pairs one of its own keys with a route.
  const routes = Object.entries(ADMIN_ROUTES) as [
    keyof typeof ADMIN_ROUTES,
    AdminRouteEntry,
  ][];

  for (const [routeKey, route] of routes) {
    const nameId = NAV_ITEM_IDS[routeKey];
    if (nameId === null) continue;
    if (HIDDEN_FOR_PILOT.has(routeKey)) continue;
    if (!userCanAccess(route.requiredPermission)) continue;
    if (route.visibleWhen && !route.visibleWhen(flags)) continue;

    const disabled =
      route.requiredTier !== null &&
      !tierAtLeast(flags.tier, route.requiredTier);

    const item: SidebarItemEntry = {
      nameId,
      icon: route.icon,
      link: route.path,
      sectionId: sectionIdFor(route.section),
      disabled,
      requiredTier: route.requiredTier,
      beta: route.beta,
    };

    // INDEX_SETTINGS surfaces a reindexing-needed error indicator
    if (route.path === ADMIN_ROUTES.INDEX_SETTINGS.path) {
      item.error = settings?.needs_reindexing;
    }

    items.push(item);
  }

  // Order the sidebar by section (stable within a section); unlabeled entries go last.
  const rank = (id: AdminNavSectionId | null) => {
    const i = NAV_SECTION_IDS.findIndex(([, sid]) => sid === id);
    return i === -1 ? NAV_SECTION_IDS.length : i;
  };
  items.sort((a, b) => rank(a.sectionId) - rank(b.sectionId));

  // No "Upgrade plan" entry: plans and billing are hidden for the pilot.
  return items;
}

/** Preserve section ordering while grouping consecutive items by section. */
export function groupBySection(items: SidebarItemEntry[]) {
  const groups: {
    sectionId: AdminNavSectionId | null;
    items: SidebarItemEntry[];
  }[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.sectionId === item.sectionId) {
      last.items.push(item);
    } else {
      groups.push({ sectionId: item.sectionId, items: [item] });
    }
  }
  return groups;
}
