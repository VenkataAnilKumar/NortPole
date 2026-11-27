"use client";

import { useNavigation, usePathname, useSearchParams } from "@opal/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Button,
  InputSwitch,
  InputTypeIn,
  LineItemButton,
  Popover,
  Text,
} from "@opal/components";
import { SvgChevronRight, SvgCodeFile, SvgPlug } from "@opal/icons";
import { Section } from "@opal/layouts";
import { IconLoader } from "@opal/loaders";
import { useFocusOnMount } from "@opal/hooks";
import type { ComposerSelection } from "@/app/app/types";
import type { MinimalAgent } from "@/lib/agents/types";
import {
  chatPluginsForAgent,
  isChatPluginEnabled,
  memberPluginsHref,
  setChatPluginEnabled,
} from "@/lib/plugins/chat";
import {
  memberPluginName,
  memberPluginReference,
  useMemberPlugins,
  type MemberPlugin,
} from "@/lib/plugins/member";
import useScreenSize from "@/hooks/useScreenSize";
import { useAppPosition } from "@/lib/navigation/hooks";
import type { ToolConfigurationHandle } from "@/lib/tools/hooks";
import { getActionIcon } from "@/lib/tools/utils";

export interface ChatPluginsPopoverProps {
  agent: MinimalAgent;
  toolConfiguration: ToolConfigurationHandle;
  disabled?: boolean;
  catalog: ReturnType<typeof useMemberPlugins>;
  onConnect: (plugin: MemberPlugin) => void;
  onBrowse: () => void;
  composerSelection?: {
    hasSelection: (item: ComposerSelection) => boolean;
    toggleSelection: (item: ComposerSelection) => void;
  };
}

export default function ChatPluginsPopover({
  agent,
  toolConfiguration,
  disabled = false,
  catalog,
  onConnect,
  onBrowse,
  composerSelection,
}: ChatPluginsPopoverProps) {
  const t = useTranslations("actions.memberPlugins");
  const quickAdd = useTranslations("chat.quickAdd");
  const { plugins, isLoading, errors, refresh } = catalog;
  const appPosition = useAppPosition();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const navigation = useNavigation();
  const { isMobile } = useScreenSize();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const trigger = useRef<HTMLElement | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const focusOnMount = useFocusOnMount<HTMLInputElement>();
  const attached = useMemo(
    () => chatPluginsForAgent(plugins, agent),
    [plugins, agent]
  );
  const matching = attached.filter(({ plugin }) =>
    memberPluginName(plugin)
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase())
  );
  const hasError = Boolean(errors.servers || errors.tools || errors.oauth);
  const returnTo =
    pathname === "/app"
      ? `/app?${searchParams.toString()}`
      : `/app?agentId=${agent.id}`;

  const browseLink = navigation.linkTo(
    composerSelection ? "/app/sources/integrations" : memberPluginsHref(returnTo)
  );
  const menuLabel = composerSelection ? quickAdd("integrations") : t("chat.trigger.label");
  const searchLabel = composerSelection ? quickAdd("searchIntegrations") : t("chat.search.placeholder");

  function handleBrowse(event: React.MouseEvent<HTMLElement>) {
    if (appPosition.chat() === null) {
      toolConfiguration.handOffToNewChatWith(agent.id, appPosition.project());
    }
    setOpen(false);
    onBrowse();
    browseLink.onClick(event);
  }

  function connect(plugin: MemberPlugin) {
    setOpen(false);
    onConnect(plugin);
  }

  function cancelHover() {
    if (hoverTimer.current !== null) clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
  }

  function hover(next: boolean) {
    cancelHover();
    if (disabled && next) return;
    hoverTimer.current = setTimeout(() => changeOpen(next), next ? 100 : 250);
  }

  function changeOpen(next: boolean) {
    cancelHover();
    if (disabled && next) return;
    setOpen(next);
    if (next && !open) setSearch("");
  }

  useEffect(
    () => () => {
      if (hoverTimer.current !== null) clearTimeout(hoverTimer.current);
    },
    []
  );

  return (
    <>
      <Popover open={open} onOpenChange={changeOpen}>
        <Popover.Trigger asChild>
          {composerSelection ? (
            <Button
              icon={SvgPlug}
              aria-label={menuLabel}
              tooltip={menuLabel}
              prominence="tertiary"
              disabled={disabled}
              interaction={open ? "hover" : "rest"}
            />
          ) : (
          <LineItemButton
            font="main-ui-action"
            ref={trigger}
            disabled={disabled}
            icon={SvgPlug}
            title={t("chat.trigger.label")}
            rounding={2}
            interaction={open ? "hover" : "rest"}
            aria-label={t("chat.trigger.label")}
            rightChildren={
              <Section
                width={1.5}
                height={1.5}
                justifyContent="center"
                alignItems="center"
              >
                <SvgChevronRight size={16} />
              </Section>
            }
            onPointerEnter={(event) => {
              if (event.pointerType === "mouse") hover(true);
            }}
            onPointerLeave={(event) => {
              if (event.pointerType === "mouse") hover(false);
            }}
            onFocus={cancelHover}
            onClick={(event) => {
              event.preventDefault();
              changeOpen(true);
            }}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight") return;
              event.preventDefault();
              event.stopPropagation();
              changeOpen(true);
            }}
          />
          )}
        </Popover.Trigger>
        <Popover.Content
          // No room beside the parent menu on phones, so open over it.
          side={composerSelection || isMobile ? "top" : "right"}
          align={composerSelection || isMobile ? "start" : "end"}
          alignOffset={composerSelection || isMobile ? 0 : -5}
          width={60}
          aria-label={menuLabel}
          onPointerEnter={cancelHover}
          onPointerLeave={(event) => {
            if (!composerSelection && event.pointerType === "mouse") hover(false);
          }}
          onCloseAutoFocus={(event) => {
            if (!composerSelection) event.preventDefault();
          }}
          onEscapeKeyDown={(event) => {
            if (composerSelection) return;
            event.preventDefault();
            event.stopPropagation();
            setOpen(false);
            trigger.current?.focus();
          }}
          onKeyDown={(event) => {
            if (composerSelection || event.key !== "ArrowLeft") return;
            if (
              event.target instanceof HTMLInputElement &&
              event.target.selectionStart !== 0
            )
              return;
            event.preventDefault();
            event.stopPropagation();
            setOpen(false);
            trigger.current?.focus();
          }}
        >
          <Popover.Menu
            gap={1}
            footer={
              <LineItemButton
                font="main-ui-action"
                title={composerSelection ? quickAdd("manageIntegrations") : t("chat.browse.label")}
                icon={SvgPlug}
                href={browseLink.href}
                onClick={handleBrowse}
                padding={0}
                rounding={2}
              />
            }
          >
            {[
              <InputTypeIn
                key="search"
                ref={focusOnMount}
                icon="search"
                variant="internal"
                value={search}
                placeholder={searchLabel}
                aria-label={searchLabel}
                onChange={(event) => setSearch(event.target.value)}
              />,
              composerSelection && <Text key="heading" font="secondary-body" color="text-04">{menuLabel}</Text>,
              isLoading && (
                <div
                  key="loading"
                  role="status"
                  className="flex items-center gap-2 p-2"
                >
                  <IconLoader size={16} />
                  <Text font="secondary-body" color="text-03">
                    {t("chat.loading.label")}
                  </Text>
                </div>
              ),
              hasError && (
                <div
                  key="error"
                  role="alert"
                  className="flex flex-col gap-2 p-2"
                >
                  <Text font="secondary-body" color="status-error-05">
                    {t("chat.loadError.text")}
                  </Text>
                  <Button
                    size="sm"
                    prominence="secondary"
                    onClick={() => void refresh()}
                  >
                    {t("chat.retry.label")}
                  </Button>
                </div>
              ),
              ...matching.map((group) => {
                const { plugin } = group;
                const reference = memberPluginReference(plugin);
                const name = memberPluginName(plugin);
                const needsConnection =
                  plugin.connection.kind === "oauth" ||
                  plugin.connection.kind === "credentials";
                const unavailable =
                  plugin.connection.kind === "checking" ||
                  plugin.connection.kind === "unconfigured" ||
                  plugin.connection.kind === "unavailable";
                const selection: ComposerSelection = {
                  kind: "integration", id: `${reference.kind}:${reference.id}`, label: name,
                };
                const enabled = composerSelection
                  ? composerSelection.hasSelection(selection)
                  : isChatPluginEnabled(group, toolConfiguration);
                return (
                  <LineItemButton
                    font="main-ui-action"
                    key={`${reference.kind}:${reference.id}`}
                    title={name}
                    titleMaxLines={1}
                    description={
                      plugin.connection.kind === "connected"
                        ? (composerSelection ? quickAdd("connected") : undefined)
                        : needsConnection
                          ? undefined
                          : t(`chat.connection.${plugin.connection.kind}`)
                    }
                    descriptionMaxLines={1}
                    icon={
                      plugin.kind === "mcp"
                        ? getActionIcon(
                            plugin.server.server_url,
                            plugin.server.name
                          )
                        : SvgCodeFile
                    }
                    padding={0}
                    rounding={2}
                    presentational
                    rightChildren={
                      needsConnection ? (
                        <Button
                          size="sm"
                          prominence="secondary"
                          disabled={disabled}
                          onClick={() => connect(plugin)}
                        >
                          {t("chat.connect.label")}
                        </Button>
                      ) : (
                        <InputSwitch
                          checked={enabled}
                          disabled={
                            disabled ||
                            !toolConfiguration.ready ||
                            (unavailable && !enabled)
                          }
                          aria-label={t("chat.toggle.ariaLabel", { name })}
                          onCheckedChange={(enabled) => {
                            if (composerSelection) {
                              composerSelection.toggleSelection(selection);
                            } else {
                              setChatPluginEnabled(group, enabled, toolConfiguration);
                            }
                          }}
                        />
                      )
                    }
                  />
                );
              }),
              !isLoading && !hasError && matching.length === 0 && (
                <div key="empty" className="p-2">
                  <Text font="secondary-body" color="text-03">
                    {composerSelection
                      ? quickAdd(search ? "noMatches" : "noIntegrations")
                      : t(search ? "chat.empty.searchText" : "chat.empty.text")}
                  </Text>
                </div>
              ),
            ]}
          </Popover.Menu>
        </Popover.Content>
      </Popover>
    </>
  );
}
