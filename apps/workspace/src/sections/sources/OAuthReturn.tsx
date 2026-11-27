"use client";

import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { NavLink } from "@opal/navigation";
import { useNavigation, useSearchParams } from "@opal/navigation";
import { card, h1Class, pageClass } from "@/sections/sources/shared";
import { CATALOG_URL } from "@/sections/sources/integrations";

/**
 * Where a service sends the person back after they sign in. It hands the code and the sealed state to the server in a POST
 * (so no GET request ever changes anything), clears them from the address bar at once, and returns to Integrations.
 */
export default function OAuthReturn() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const params = useSearchParams();
  const navigation = useNavigation();
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = params.get("code");
    const sealed = params.get("state");
    navigation.go("/app/sources/oauth", { replace: true });
    if (params.get("error") || !code || !sealed) {
      setState({ ok: false, text: "Signing in was cancelled or the service did not send a code. Nothing was connected." });
      return;
    }
    fetch(`${CATALOG_URL}/oauth/complete`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: sealed, code }) })
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Signing in failed. Start again from Integrations.");
        setState({ ok: true, text: `Connected ${data?.name ?? "your account"}.` });
        window.setTimeout(() => navigation.go("/app/sources/integrations", { replace: true }), 1200);
      })
      .catch((e: unknown) => setState({ ok: false, text: e instanceof Error ? e.message : "Signing in failed." }));
  }, [params, navigation]);

  return (
    <div className={pageClass} data-testid="oauth-return">
      <h1 className={h1Class}>{workspaceText("signingIn")}</h1>
      <section className={card} aria-live="polite">
        <p className={`text-sm ${state?.ok === false ? "text-status-text-error-05" : "text-text-05"}`} role={state?.ok === false ? "alert" : "status"}>{state?.text ?? "Finishing sign-in…"}</p>
        {state && <p className="mt-2 text-sm text-text-03"><NavLink href="/app/sources/integrations" className="font-semibold text-text-05 underline">{workspaceText("backToIntegrations")}</NavLink></p>}
      </section>
    </div>
  );
}
