"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useId, useState } from "react";
import { useRoutePolicy } from "@/lib/routePolicy/hooks";
import { saveUserPreferences, useUserPreferences, type DefaultRoute } from "@/lib/userPreferences/hooks";
import type { RouteKind } from "@/lib/routePolicy/types";

const KIND_LABEL: Record<RouteKind, string> = { local: "Local", private: "Private", cloud: "Cloud" };
const KIND_HELP: Record<RouteKind, string> = {
  local: "Runs on your organization's own hardware",
  private: "Customer-controlled private inference",
  cloud: "Third-party cloud provider",
};

const card = "rounded-2xl border border-border-01 bg-background-neutral-00 p-5 shadow-sm";

/** Personal model settings: a default route for new tasks, and the routes your administrator allows. */
export default function ModelsSettings() {
  const inputPrefix = useId();
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const { data: policy } = useRoutePolicy();
  const { data: prefs } = useUserPreferences();
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle");
  const pref: DefaultRoute = prefs?.default_route ?? "auto";

  const choose = async (v: DefaultRoute) => {
    if (!prefs) return;
    try {
      await saveUserPreferences({ ...prefs, default_route: v });
      setStatus("saved");
    } catch {
      setStatus("error");
    }
    window.setTimeout(() => setStatus("idle"), 2500);
  };

  const options: { value: DefaultRoute; label: string; help: string }[] = [
    { value: "auto", label: "Auto", help: "Best allowed route for each task" },
    ...(["local", "private", "cloud"] as RouteKind[]).map((k) => ({ value: k as DefaultRoute, label: KIND_LABEL[k], help: KIND_HELP[k] })),
  ];

  const blockedPref =
    policy && pref !== "auto" && !policy.routes.some((r) => r.kind === pref && r.allowed);

  return (
    <ResponsiveLayout display="flex" className="flex-col gap-6" data-testid="models-settings">
      <section className={card} aria-labelledby="ms-default">
        <h2 id="ms-default" className="mb-1 text-base font-semibold text-text-05">{workspaceText("defaultRoute")}</h2>
        <p className="mb-4 text-sm text-text-03">{workspaceText("whereNewTasksRunUnlessYouPickAnotherRoute")}</p>
        <ResponsiveLayout display="flex" role="radiogroup" aria-label={workspaceText("defaultRoute")} className="flex-col gap-2">
          {options.map((o) => (
            <ResponsiveLayout
              key={o.value}
              display="flex"
              className={`min-h-12 items-center gap-3 rounded-xl border px-4 py-2 ${pref === o.value ? "border-text-05 bg-background-neutral-01" : "border-border-01"}`}
            >
              <NativeInput
                id={inputPrefix + o.value}
                aria-describedby={inputPrefix + o.value + "-help"}
                type="radio"
                name="default-route"
                className="h-4 w-4"
                checked={pref === o.value}
                onChange={() => choose(o.value)}
              />
              <span>
                <label htmlFor={inputPrefix + o.value} className="block cursor-pointer text-sm font-semibold text-text-05">{o.label}</label>
                <span id={inputPrefix + o.value + "-help"} className="block text-xs text-text-03">{o.help}</span>
              </span>
            </ResponsiveLayout>
          ))}
        </ResponsiveLayout>
        {status === "saved" && (
          <p role="status" className="mt-3 text-sm text-status-success-05">{workspaceText("saved")}</p>
        )}
        {status === "error" && (
          <p role="alert" className="mt-3 text-sm text-status-text-error-05">{workspaceText("couldNotSaveTryAgainInAMoment")}</p>
        )}
        {blockedPref && (
          <p role="status" className="mt-3 text-sm text-status-text-error-05">{workspaceText("yourAdministratorSPolicyDoesNotCurrentlyAllow")}{" "}{KIND_LABEL[pref as RouteKind]}{" "}{workspaceText("routesForThisWorkspaceSDataSoAutoIs")}</p>
        )}
        <p className="mt-3 text-xs text-text-03">{workspaceText("savedToYourAccountSoItFollowsYouTo")}</p>
      </section>

      <section className={card} aria-labelledby="ms-routes">
        <h2 id="ms-routes" className="mb-1 text-base font-semibold text-text-05">{workspaceText("routesYouCanUse")}</h2>
        <p className="mb-4 text-sm text-text-03">
          {policy
            ? `This workspace treats data as ${policy.data_class} (policy v${policy.version}).`
            : "Loading the policy…"}
        </p>
        {policy && policy.routes.length === 0 && <p className="text-sm text-text-03">{workspaceText("noModelRoutesAreSetUpYet")}</p>}
        <ul className="divide-y divide-border-01">
          {policy?.routes.map((r) => (
            <li key={r.provider_id} className="flex flex-wrap items-center gap-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-text-05">
                  {KIND_LABEL[r.kind]} <span className="font-normal text-text-03">· {r.name ?? r.provider}</span>
                </div>
                <div className="text-xs text-text-03">{r.allowed ? KIND_HELP[r.kind] : (r.reason ?? "Not allowed by policy")}</div>
              </div>
              <span
                className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${r.allowed ? "bg-status-success-01 text-status-success-05" : "bg-status-error-01 text-status-text-error-05"}`}
              >
                {r.allowed ? "Allowed" : "Blocked"}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </ResponsiveLayout>
  );
}
