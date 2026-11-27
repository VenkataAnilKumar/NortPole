"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useRef, useState } from "react";
import { Button } from "@opal/components";
import {
  SvgChevronRight,
  SvgFiles,
  SvgFolder,
  SvgLinkedDots,
  SvgPlusCircle,
  SvgSearch,
} from "@opal/icons";
import { useNavigation } from "@opal/navigation";
import { useDocumentSets } from "@/app/admin/documents/sets/hooks";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import type { ValidSources } from "@/lib/connectors/types/source";
import { getSourceDisplayName } from "@/lib/connectors/utils";
import { usePermissionAuthority } from "@/lib/permissions/hooks";
import { can } from "@/lib/permissions/resource-actions";
import { useSettings } from "@/lib/settings/hooks";
import { type DocumentSetSummary, Permission } from "@/lib/types";
import { useUser } from "@/providers/UserProvider";
import { workspaceSourceKey } from "@/sections/sources/integrations";
import PolicyRulesPanel from "./PolicyRulesPanel";
import CollectionDocuments from "./CollectionDocuments";
import PersonalKnowledge from "./PersonalKnowledge";

const scopes = ["All collections", "Company", "Restricted"] as const;
const surface = "rounded-2xl border border-border-01 bg-background-neutral-00";

function visibility(collection: DocumentSetSummary) {
  return collection.is_public ? "Company" : "Restricted";
}

function CollectionDetails({
  collection,
  enabled,
}: {
  collection: DocumentSetSummary;
  enabled: boolean;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const navigation = useNavigation();
  const sources = [
    ...collection.cc_pair_summaries.map((source) => ({ ...source, key: `connected-${source.id}` })),
    ...(collection.federated_connector_summaries ?? []).map((source) => ({
      ...source,
      key: `federated-${source.id}`,
    })),
  ];
  return (
    <ResponsiveLayout display="flex" className="min-w-0 flex-col gap-5">
      <header className="flex flex-col gap-2 border-b border-border-01 pb-4">
        <p className="text-sm text-text-03">{visibility(collection)} collection</p>
        <h2
          id="collection-title"
          className="break-words font-[family-name:var(--font-serif)] text-2xl text-text-05"
        >
          {collection.name}
        </h2>
        {collection.description && (
          <p className="break-words text-sm text-text-03">{collection.description}</p>
        )}
        <ResponsiveLayout display="flex" className="mt-1 flex-wrap items-center gap-3">
          <span
            className={`rounded-full px-2 py-1 text-xs ${collection.is_up_to_date ? "bg-status-success-01 text-status-success-05" : "bg-status-warning-01 text-status-text-warning-05"}`}
          >
            {collection.is_up_to_date ? "Up to date" : "Syncing"}
          </span>
          {enabled &&
            can(collection, "edit") &&
            (collection.is_up_to_date ? (
              <Button
                prominence="secondary"
                {...navigation.linkTo(`/admin/documents/sets/${collection.id}`)}
              >{workspaceText("editCollection")}</Button>
            ) : (
              <span className="text-xs text-text-03">{workspaceText("editingIsAvailableAfterSync")}</span>
            ))}
        </ResponsiveLayout>
      </header>
      <section aria-labelledby="collection-sources" className="flex flex-col gap-2">
        <h3 id="collection-sources" className="font-semibold text-text-05">{workspaceText("sources_25464d")}{sources.length})
        </h3>
        {sources.length ? (
          <ul className="flex flex-wrap gap-2">
            {sources.map((source) => (
              <li
                key={source.key}
                className="flex max-w-full items-center gap-2 rounded-lg border border-border-01 px-2.5 py-1.5 text-sm text-text-03"
              >
                <SvgLinkedDots size={16} className="shrink-0" />
                <span className="min-w-0 break-words">{source.name || source.source}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-text-03">{workspaceText("noSourcesInThisCollection")}</p>
        )}
      </section>
      {enabled && can(collection, "edit") && <PolicyRulesPanel key={`policy-rules-${collection.id}`} id={collection.id} name={collection.name} />}
      {enabled && <CollectionDocuments key={collection.id} collectionId={collection.id} />}
    </ResponsiveLayout>
  );
}

export default function LibrariesPage({ sourceFilter }: { sourceFilter?: ValidSources }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const navigation = useNavigation();
  const { vectorDbEnabled, vector_db_enabled, user_knowledge_enabled } = useSettings();
  const { user } = useUser();
  const { data: collections, error, isLoading, mutate } = useDocumentSets();
  const { isGlobalHolder: canConnect, isScopedManager: canOperateConnectors } =
    usePermissionAuthority(Permission.MANAGE_CONNECTORS);
  const { isGlobalHolder: canManageSets, isScopedManager: canManageScopedSets } =
    usePermissionAuthority(Permission.MANAGE_DOCUMENT_SETS);
  const canManageCollections = canManageSets || canManageScopedSets;
  const hasPersonalFiles = !!user && !user.is_anonymous_user && user_knowledge_enabled === true;
  const [view, setView] = useState<"collections" | "files">("collections");
  const [scope, setScope] = useState<(typeof scopes)[number]>("All collections");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number>();
  const [mobileDetails, setMobileDetails] = useState(false);
  const detailRef = useRef<HTMLElement>(null);
  const lastCollectionButton = useRef<HTMLButtonElement>(null);
  const query = search.trim().toLowerCase();
  const sourceName = sourceFilter && (getSourceDisplayName(sourceFilter) ?? sourceFilter);
  const visible = (collections ?? []).filter(
    (collection) =>
      (!sourceFilter ||
        collection.cc_pair_summaries.some((source) => workspaceSourceKey(source.source) === sourceFilter) ||
        collection.federated_connector_summaries?.some((source) => workspaceSourceKey(source.source) === sourceFilter)) &&
      (scope === "All collections" || scope === visibility(collection)) &&
      (!query ||
        [collection.name, collection.description].some((value) =>
          value?.toLowerCase().includes(query),
        )),
  );
  const selected = visible.find((collection) => collection.id === selectedId) ?? visible[0];

  return (
    <main
      className="mx-auto flex w-full max-w-6xl flex-col gap-5 p-4 sm:p-8"
      data-testid="knowledge-page"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-[family-name:var(--font-serif)] text-3xl text-text-05">{workspaceText("knowledge")}</h1>
          <p className="mt-1 text-sm text-text-03">{workspaceText("browseSharedCollectionsAndManageYourPersonalFiles")}</p>
        </div>
        {vectorDbEnabled && canManageCollections && (
          <Button icon={SvgPlusCircle} {...navigation.linkTo("/admin/documents/sets/new")}>{workspaceText("createCollection")}</Button>
        )}
      </header>

      {hasPersonalFiles && (
        <nav aria-label={workspaceText("knowledgeViews")} className="flex gap-1 border-b border-border-01 pb-2">
          <Button
            icon={SvgFolder}
            prominence={view === "collections" ? "primary" : "tertiary"}
            aria-pressed={view === "collections"}
            onClick={() => setView("collections")}
          >{workspaceText("collections")}</Button>
          <Button
            icon={SvgFiles}
            prominence={view === "files" ? "primary" : "tertiary"}
            aria-pressed={view === "files"}
            onClick={() => setView("files")}
          >{workspaceText("myFiles")}</Button>
        </nav>
      )}
      {view === "files" && hasPersonalFiles ? (
        <div className={`${surface} p-4 sm:p-5`}>
          <PersonalKnowledge />
        </div>
      ) : (
        <>
          {vector_db_enabled === false && (
            <p className="text-sm text-text-03">{workspaceText("knowledgeRetrievalIsDisabledAnAdministratorMustEnableThe")}</p>
          )}
          <ResponsiveLayout display="grid" className="min-w-0 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <section
              aria-label={workspaceText("collections")}
              className={`${surface} min-w-0 p-4 ${mobileDetails && selected ? "hidden lg:block" : ""}`}
            >
              {sourceName && (
                <ResponsiveLayout display="flex" className="mb-3 flex-wrap items-center justify-between gap-2 rounded-lg border border-border-01 px-3 py-2">
                  <p className="text-sm font-medium text-text-05">
                    {workspaceText("collectionsUsingSource", { source: sourceName })}
                  </p>
                  <Button prominence="tertiary" {...navigation.linkTo("/app/knowledge")}>
                    {workspaceText("clearSourceFilter")}
                  </Button>
                </ResponsiveLayout>
              )}
              <label className="flex min-w-0 items-center gap-2 rounded-lg border border-border-01 px-3 focus-within:ring-2 focus-within:ring-text-05">
                <SvgSearch size={18} className="shrink-0 text-text-03" />
                <NativeInput
                  type="search"
                  aria-label={workspaceText("searchCollections")}
                  placeholder={workspaceText("searchCollections")}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="h-10 min-w-0 flex-1 bg-transparent text-sm text-text-05 outline-none"
                />
              </label>
              <ResponsiveLayout display="flex"
                role="group"
                aria-label={workspaceText("collectionVisibility")}
                className="my-3 flex-wrap gap-1"
              >
                {scopes.map((option) => (
                  <ActionButton
                    key={option}
                    type="button"
                    aria-pressed={scope === option}
                    onClick={() => setScope(option)}
                    className={`rounded-md px-2 py-1.5 text-xs font-medium focus-visible:outline-2 ${scope === option ? "bg-background-neutral-02 text-text-05" : "text-text-03 hover:bg-background-neutral-01"}`}
                  >
                    {option}
                  </ActionButton>
                ))}
              </ResponsiveLayout>
              {error ? (
                <ResponsiveLayout display="flex" className="flex-col items-start gap-2 p-2">
                  <p role="alert" className="text-sm text-text-03">{workspaceText("couldNotLoadCollections")}</p>
                  <Button prominence="secondary" onClick={() => void mutate()}>{workspaceText("tryAgain")}</Button>
                </ResponsiveLayout>
              ) : isLoading ? (
                <p role="status" className="p-2 text-sm text-text-03">{workspaceText("loadingCollections")}</p>
              ) : visible.length ? (
                <ul className="flex flex-col gap-1">
                  {visible.map((collection) => (
                    <li key={collection.id}>
                      <ActionButton
                        type="button"
                        aria-current={selected?.id === collection.id ? "true" : undefined}
                        onClick={(event) => {
                          lastCollectionButton.current = event.currentTarget;
                          setSelectedId(collection.id);
                          setMobileDetails(true);
                          requestAnimationFrame(() => detailRef.current?.focus());
                        }}
                        className="flex min-h-14 w-full min-w-0 items-center gap-3 rounded-lg border border-transparent px-3 py-2 text-start hover:bg-background-neutral-01 focus-visible:outline-2 aria-[current=true]:border-border-01 aria-[current=true]:bg-background-neutral-02"
                      >
                        <SvgFolder size={18} className="shrink-0 text-text-03" />
                        <span className="min-w-0 flex-1">
                          <span className="block break-words text-sm font-semibold text-text-05">
                            {collection.name}
                          </span>
                          <span className="block text-xs text-text-03">
                            {visibility(collection)} ·{" "}
                            {collection.is_up_to_date ? "Up to date" : "Syncing"}
                          </span>
                        </span>
                        <SvgChevronRight size={16} className="shrink-0 text-text-03" />
                      </ActionButton>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="p-2 text-sm text-text-03">
                  {sourceFilter || query || scope !== "All collections"
                    ? "No matching collections."
                    : "No collections available to you yet."}
                </p>
              )}
              {vectorDbEnabled && (canConnect || canOperateConnectors) && (
                <ResponsiveLayout display="flex" className="mt-4 flex-wrap gap-2 border-t border-border-01 pt-3">
                  {canConnect && (
                    <Button
                      prominence="secondary"
                      {...navigation.linkTo(ADMIN_ROUTES.CONNECTORS.path)}
                    >{workspaceText("connectSource")}</Button>
                  )}
                  <Button
                    prominence="secondary"
                    {...navigation.linkTo(ADMIN_ROUTES.INDEXING_STATUS.path)}
                  >{workspaceText("indexingStatus")}</Button>
                </ResponsiveLayout>
              )}
            </section>
            {selected && !error && (
              <section
                ref={detailRef}
                tabIndex={-1}
                aria-labelledby="collection-title"
                className={`${surface} min-w-0 p-4 sm:p-5 ${mobileDetails ? "block" : "hidden lg:block"}`}
              >
                <div className="mb-4 lg:hidden">
                  <Button
                    prominence="secondary"
                    onClick={() => {
                      setMobileDetails(false);
                      requestAnimationFrame(() => lastCollectionButton.current?.focus());
                    }}
                  >{workspaceText("backToCollections")}</Button>
                </div>
                <CollectionDetails collection={selected} enabled={vectorDbEnabled} />
              </section>
            )}
          </ResponsiveLayout>
        </>
      )}
    </main>
  );
}
