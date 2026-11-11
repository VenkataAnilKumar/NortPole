"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRoutePolicy } from "@/lib/routePolicy/hooks";
import type { RouteKind, RouteView } from "@/lib/routePolicy/types";
import type { LLMProviderDescriptor } from "@/lib/languageModels/types";
import type { SelectedModel } from "@/sections/model-selector/MultiModelSelector";
import { getDefaultRoute } from "@/lib/routePolicy/preferences";

const KIND_LABEL: Record<RouteKind, string> = {
  local: "Local",
  private: "Private",
  cloud: "Cloud",
};

const KIND_HELP: Record<RouteKind, string> = {
  local: "Runs on your organization's own hardware",
  private: "Customer-controlled private inference",
  cloud: "Third-party cloud provider",
};

interface RoutePickerProps {
  selectedModels: SelectedModel[];
  onReplace: (index: number, model: SelectedModel) => void;
  providers: LLMProviderDescriptor[] | undefined;
  /** Which way the menu opens; use "up" when the picker sits above the input. */
  direction?: "up" | "down";
}

/**
 * Choose where a task runs. Routes come from the administrator's policy: a route
 * the policy blocks for the workspace's data class stays listed but disabled,
 * with the reason. A blocked route is also refused by the server before any
 * content is sent. The choice is a preference inside the policy and never
 * overrides it.
 */
export default function RoutePicker({
  selectedModels,
  onReplace,
  providers,
  direction = "down",
}: RoutePickerProps) {
  const { data: policy } = useRoutePolicy();
  const [open, setOpen] = useState(false);
  const [autoMode, setAutoMode] = useState(true);
  const appliedDefault = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (rootRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const providerById = useMemo(() => {
    const m = new Map<number, LLMProviderDescriptor>();
    (providers ?? []).forEach((p) => m.set(p.id, p));
    return m;
  }, [providers]);

  const current = selectedModels[0];
  const currentRoute: RouteView | undefined = useMemo(() => {
    if (!policy || !current) return undefined;
    return policy.routes.find((r) => {
      const p = providerById.get(r.provider_id);
      return p?.model_configurations.some(
        (mc) => mc.id === current.modelConfigurationId
      );
    });
  }, [policy, current, providerById]);

  const pick = (providerId: number) => {
    const p = providerById.get(providerId);
    const mc = p?.model_configurations.find((m) => m.is_visible) ?? p?.model_configurations[0];
    if (!p || !mc) return;
    onReplace(0, {
      name: p.name ?? p.provider,
      provider: p.provider,
      modelName: mc.name,
      modelConfigurationId: mc.id ?? null,
      displayName: mc.display_name || mc.name,
    });
  };

  // Honour the saved default route once, on the home screen only (a new task).
  // An open chat keeps the model it already uses.
  useEffect(() => {
    if (direction !== "down" || appliedDefault.current || !policy || !providers?.length) return;
    appliedDefault.current = true;
    const pref = getDefaultRoute();
    const target =
      pref === "auto"
        ? policy.auto_provider_id
        : (policy.routes.find((r) => r.kind === pref && r.allowed && r.model_names.length > 0)?.provider_id ?? null);
    if (target == null) return;
    setAutoMode(pref === "auto");
    pick(target);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policy, providers, direction]);

  if (!policy || policy.routes.length === 0) return null;

  const chooseAuto = () => {
    setAutoMode(true);
    if (policy.auto_provider_id != null) pick(policy.auto_provider_id);
    setOpen(false);
  };

  const chooseRoute = (r: RouteView) => {
    if (!r.allowed) return;
    setAutoMode(false);
    pick(r.provider_id);
    setOpen(false);
  };

  const label = autoMode
    ? "Auto"
    : currentRoute
      ? KIND_LABEL[currentRoute.kind]
      : "Route";
  const blockedNow = currentRoute ? !currentRoute.allowed : false;

  return (
    <div ref={rootRef} className="relative" data-testid="route-picker">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setAnchor(rootRef.current?.getBoundingClientRect() ?? null);
          setOpen((v) => !v);
        }}
        className="flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-border-01 bg-background-neutral-00 px-3 py-1.5 text-sm font-medium text-text-05 shadow-sm hover:bg-background-neutral-01"
      >
        <span className="text-text-03">Run on</span>
        <span>{label}</span>
        {blockedNow && (
          <span className="rounded-full bg-status-error-01 px-2 text-xs text-status-error-05">
            Blocked
          </span>
        )}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && anchor && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          style={
            direction === "up"
              ? { position: "fixed", right: window.innerWidth - anchor.right, bottom: window.innerHeight - anchor.top + 8 }
              : { position: "fixed", right: window.innerWidth - anchor.right, top: anchor.bottom + 8 }
          }
          role="menu"
          aria-label="Model route"
          className="z-[60] w-[22rem] rounded-2xl border border-border-01 bg-background-neutral-00 p-2 shadow-lg"
        >
          <p className="px-3 pb-1 pt-2 text-xs text-text-03">
            This workspace treats data as{" "}
            <strong className="text-text-05">{policy.data_class}</strong>. Your
            administrator allows these routes (policy v{policy.version}).
          </p>
          <button
            type="button"
            role="menuitemradio"
            aria-checked={autoMode}
            onClick={chooseAuto}
            className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left hover:bg-background-neutral-01"
          >
            <span>
              <span className="block text-sm font-semibold text-text-05">Auto</span>
              <span className="block text-xs text-text-03">Best allowed route for this task</span>
            </span>
            {autoMode && <span className="rounded-full bg-background-neutral-02 px-2 py-0.5 text-xs">Selected</span>}
          </button>
          {policy.routes.map((r) => {
            const selected = !autoMode && currentRoute?.provider_id === r.provider_id;
            return (
              <button
                key={r.provider_id}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                aria-disabled={!r.allowed}
                disabled={!r.allowed}
                title={r.reason ?? undefined}
                onClick={() => chooseRoute(r)}
                className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left hover:bg-background-neutral-01 disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:bg-transparent"
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-text-05">
                    {KIND_LABEL[r.kind]} <span className="font-normal text-text-03">· {r.name ?? r.provider}</span>
                  </span>
                  <span className="block text-xs text-text-03">
                    {r.allowed ? KIND_HELP[r.kind] : (r.reason ?? "Not allowed by policy")}
                  </span>
                </span>
                {r.allowed ? (
                  selected ? (
                    <span className="rounded-full bg-background-neutral-02 px-2 py-0.5 text-xs">Selected</span>
                  ) : (
                    <span className="rounded-full bg-status-success-01 px-2 py-0.5 text-xs text-status-success-05">Allowed</span>
                  )
                ) : (
                  <span className="rounded-full bg-status-error-01 px-2 py-0.5 text-xs text-status-error-05">Blocked</span>
                )}
              </button>
            );
          })}
          {!policy.routes.every((r) => r.kind_assigned) && (
            <p className="px-3 pb-2 pt-1 text-xs text-text-03">
              Some routes have no type set; they are treated as cloud until an administrator sets one.
            </p>
          )}
        </div>,
        document.body
      )}
    </div>
  );
}
