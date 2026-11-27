"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Dropdown, SelectButton } from "@opal/components";
import { SvgGlobe } from "@opal/icons";
import { useRoutePolicy } from "@/lib/routePolicy/hooks";
import type { LlmManager } from "@/lib/hooks";
import { useUserPreferences } from "@/lib/userPreferences/hooks";

interface RoutePickerProps {
  llmManager: LlmManager;
  requiredModelId?: number | null;
  applyDefault?: boolean;
  disabled?: boolean;
}

export default function RoutePicker({
  llmManager,
  requiredModelId,
  applyDefault = false,
  disabled = false,
}: RoutePickerProps) {
  const t = useTranslations("chat.modelRoute");
  const { data: policy } = useRoutePolicy();
  const { data: prefs } = useUserPreferences();
  const appliedDefault = useRef(false);
  const {
    llmProviders,
    currentLlm,
    updateCurrentLlm,
    resetChatModel,
    chatModelMode,
    imageFilesPresent,
  } = llmManager;
  const auto = requiredModelId == null && chatModelMode !== "manual";
  const currentModelId = requiredModelId ?? currentLlm.modelConfigurationId;
  const currentProvider = llmProviders?.find(
    (provider) =>
      currentModelId != null &&
      provider.model_configurations.some(({ id }) => id === currentModelId),
  );
  const routes = (policy?.routes ?? []).map((route) => {
    const provider = llmProviders?.find(({ id }) => id === route.provider_id);
    const eligible =
      provider?.model_configurations.filter(
        (model) =>
          model.id != null &&
          model.is_visible &&
          !model.is_router &&
          model.supports_chat !== false &&
          (!imageFilesPresent || model.supports_image_input),
      ) ?? [];
    const model =
      eligible.find(({ is_recommended_default }) => is_recommended_default) ?? eligible[0];
    return { route, provider, model };
  });

  const preferred = routes.find(
    ({ route, model }) => route.kind === prefs?.default_route && route.allowed && model,
  );
  const preferredProvider = preferred?.provider;
  const preferredModel = preferred?.model;

  useEffect(() => {
    if (
      !applyDefault ||
      appliedDefault.current ||
      !policy ||
      !prefs ||
      llmManager.isLoadingProviders
    )
      return;
    appliedDefault.current = true;
    if (!auto || !preferredProvider || !preferredModel) return;
    updateCurrentLlm({
      name: preferredProvider.name ?? preferredProvider.provider,
      provider: preferredProvider.provider,
      modelName: preferredModel.name,
      modelConfigurationId: preferredModel.id,
    });
  }, [
    applyDefault,
    auto,
    llmManager.isLoadingProviders,
    policy,
    prefs,
    preferredModel,
    preferredProvider,
    updateCurrentLlm,
  ]);

  if (!routes.length) return null;
  const current = routes.find(({ route }) => route.provider_id === currentProvider?.id)?.route;
  const label = auto ? t("auto") : current ? t(current.kind) : t("label");

  return (
    <Dropdown side="top" disabled={disabled}>
      <Dropdown.Trigger asChild>
        <SelectButton
          icon={SvgGlobe}
          size="sm"
          chevron
          disabled={disabled}
          aria-label={t("selected", { route: label })}
        >
          {label}
        </SelectButton>
      </Dropdown.Trigger>
      <Dropdown.Data
        label={t("label")}
        value={auto ? "auto" : String(current?.provider_id ?? "")}
        items={[
          {
            kind: "option",
            value: "auto",
            title: t("auto"),
            description: t("autoHelp"),
            disabled: requiredModelId != null,
          },
          ...routes.map(({ route, model }) => ({
            kind: "option" as const,
            value: String(route.provider_id),
            title: `${t(route.kind)} · ${route.name ?? route.provider}`,
            description: !route.allowed
              ? (route.reason ?? t("blocked"))
              : requiredModelId != null
                ? t("agentLocked")
                : (model?.effectiveDisplayName ?? t("unavailable")),
            descriptionMaxLines: 3,
            disabled: !route.allowed || !model || requiredModelId != null,
          })),
        ]}
        onSelect={({ value }) => {
          appliedDefault.current = true;
          if (value === "auto") {
            resetChatModel?.();
            return;
          }
          const selection = routes.find(({ route }) => String(route.provider_id) === value);
          if (
            !selection?.route.allowed ||
            !selection.provider ||
            !selection.model ||
            requiredModelId != null
          )
            return;
          const { provider, model } = selection;
          updateCurrentLlm({
            name: provider.name ?? provider.provider,
            provider: provider.provider,
            modelName: model.name,
            modelConfigurationId: model.id,
          });
        }}
      />
    </Dropdown>
  );
}
