"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useMemo } from "react";
import useSWR from "swr";
import { Button } from "@opal/components";
import { useNavigation } from "@opal/navigation";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { usePermissionAuthority } from "@/lib/permissions/hooks";
import { useSettings } from "@/lib/settings/hooks";
import { Permission, type CCPairBasicInfo } from "@/lib/types";
import { SWR_KEYS } from "@/lib/swr-keys";
import IntegrationCatalog from "@/sections/sources/IntegrationCatalog";
import { card, h1Class, pageClass } from "@/sections/sources/shared";
import { workspaceIndexingBySource, workspaceSourceKey } from "@/sections/sources/integrations";

export default function IntegrationsPage({ initialIntegration }: { initialIntegration?: string }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const navigation = useNavigation();
  const { vectorDbEnabled, vector_db_enabled, show_extra_connectors } = useSettings();
  const searchDisabled = vector_db_enabled === false;
  const { isGlobalHolder: canConnect, isScopedManager: canOperateConnectors } =
    usePermissionAuthority(Permission.MANAGE_CONNECTORS);
  const { data, error, isLoading, mutate } = useSWR<{ sources: string[] }>(
    searchDisabled ? null : "/api/manage/indexed-sources",
    errorHandlingFetcher,
  );
  const { data: connectorStatus, error: indexingError, mutate: refreshIndexing } = useSWR<CCPairBasicInfo[]>(
    vectorDbEnabled ? `${SWR_KEYS.connectorStatus}?include_indexing=true` : null,
    errorHandlingFetcher,
    { refreshInterval: 10_000 },
  );
  const indexing = useMemo(() => workspaceIndexingBySource(connectorStatus ?? []), [connectorStatus]);
  const configured = useMemo(
    () =>
      new Set(
        [...(data?.sources ?? []), ...indexing.keys()]
          .filter((source) => !["ingestion_api", "user_file", "craft_file"].includes(source))
          .map(workspaceSourceKey),
      ),
    [data, indexing],
  );

  return (
    <div className={pageClass} data-testid="integrations-page">
      <header className="flex flex-col gap-1">
        <h1 className={h1Class}>{workspaceText("integrations")}</h1>
      </header>
      <section aria-labelledby="workspace-sources" className={`${card} flex flex-col gap-3`}>
        <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="workspace-sources" className="text-base font-semibold text-text-05">{workspaceText("workspaceSources")}</h2>
            <p className="mt-1 text-sm text-text-03">{workspaceText("administratorsConnectSourcesForCompanySearchDocumentAccessStill")}</p>
          </div>
          <ResponsiveLayout display="flex" className="flex-wrap gap-2">
            {vectorDbEnabled && canConnect && (
              <Button {...navigation.linkTo(ADMIN_ROUTES.CONNECTORS.path)}>{workspaceText("connectWorkspaceSource")}</Button>
            )}
            {vectorDbEnabled && (canConnect || canOperateConnectors) && (
              <Button
                prominence="secondary"
                {...navigation.linkTo(ADMIN_ROUTES.INDEXING_STATUS.path)}
              >{workspaceText("indexingStatus")}</Button>
            )}
            <Button prominence="secondary" {...navigation.linkTo("/app/knowledge")}>{workspaceText("viewKnowledge")}</Button>
          </ResponsiveLayout>
        </ResponsiveLayout>
        {searchDisabled ? (
          <p data-testid="connectors-no-search" className="text-sm text-text-03">{workspaceText("anAdministratorNeedsToEnableDocumentSearchBeforeWorkspace")}</p>
        ) : error ? (
          <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
            <p role="alert" className="text-sm text-text-03">{workspaceText("workspaceSourcesCouldNotBeLoaded")}</p>
            <Button prominence="secondary" onClick={() => void mutate()}>{workspaceText("tryAgain")}</Button>
          </ResponsiveLayout>
        ) : isLoading ? (
          <p role="status" className="text-sm text-text-03">{workspaceText("loadingWorkspaceSources")}</p>
        ) : configured.size > 0 ? (
          <p className="text-sm text-text-03">
            {configured.size} {configured.size === 1 ? "source type" : "source types"}{" "}{workspaceText("configuredForKnowledge")}</p>
        ) : (
          <p className="text-sm text-text-03">{workspaceText("noWorkspaceSourcesConfiguredYet")}</p>
        )}
        {indexingError && (
          <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
            <p role="alert" className="text-sm text-text-03">{workspaceText("workspaceReadiness.unavailable")}</p>
            <Button prominence="secondary" onClick={() => void refreshIndexing()}>{workspaceText("tryAgain")}</Button>
          </ResponsiveLayout>
        )}
      </section>
      <IntegrationCatalog
        key={initialIntegration}
        initialIntegration={initialIntegration}
        showExtraConnectors={show_extra_connectors}
        workspaceStatus={{ enabled: vectorDbEnabled, canConnect, canMonitor: canConnect || canOperateConnectors, configured, indexing }}
      />
    </div>
  );
}
