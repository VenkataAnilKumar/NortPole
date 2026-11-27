"use client";

import { useNavigation } from "@opal/navigation";
import {
  useCallback,
  useMemo,
  useState,
  useEffect,
  useLayoutEffect,
  useRef,
} from "react";
import useNotifications from "@/hooks/useNotifications";
import type { Route } from "next";
import { useTranslations } from "next-intl";
import { useSettings } from "@/lib/settings/hooks";
import { MinimalAgent } from "@/lib/agents/types";
import ChatButton from "@/sections/sidebar/ChatButton";
import { AgentButton } from "@/lib/agents/components";
import { DragEndEvent } from "@dnd-kit/core";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import useChatSessions from "@/hooks/useChatSessions";
import { useAgents, useActiveAgent, usePinnedAgents } from "@/lib/agents/hooks";
import { SidebarLoader } from "@opal/loaders";
import { SidebarLayouts, Section } from "@opal/layouts";
import BrandedSidebarHeader from "@/sections/sidebar/BrandedSidebarHeader";
import { Text } from "@opal/components";
import { cn } from "@opal/utils";
import { Disabled } from "@opal/core";
import { usePlans, useTierAtLeast } from "@/lib/tiers/hooks";
import { BetaTag, PlanTag } from "@/lib/tiers/components";
import { Tier } from "@/lib/tiers/types";
import { PHFeatureFlag, usePHFeatureFlag } from "@/lib/analytics/hooks";
import { SidebarTab } from "@opal/components";
import { ChatSession } from "@/app/app/types";
import { useUser } from "@/providers/UserProvider";
import { getFirstPermittedAdminRoute } from "@/lib/permissions/utils";
import { useAppPosition } from "@/lib/navigation/hooks";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { useUserPreferences } from "@/lib/userPreferences/hooks";
import { useOwnWork } from "@/lib/inboxWork";
import { inboxBadgeCount } from "@/lib/notifications/inbox";
import type { InboxNotificationSummary } from "@/lib/notifications/interfaces";
import { usePendingProposals } from "@/sections/inbox/IntegrationChanges";
import { useModalContext } from "@/components/context/ModalContext";
import {
  SvgDevKit,
  SvgPlug,
  SvgFiles,
  SvgStackLine,
  SvgBell,
  SvgEditBig,
  SvgFolder,
  SvgNortPoleOctagon,
  SvgSearchMenu,
  SvgSettings,
} from "@opal/icons";
import BuildModeIntroBackground from "@/app/craft/components/IntroBackground";
import BuildModeIntroContent from "@/app/craft/components/IntroContent";
import { CRAFT_PATH } from "@/app/craft/v1/constants";
import UnseenMarker from "@/app/craft/components/UnseenMarker";
import { useUnviewedScheduledTaskCount } from "@/lib/scheduledTasks/hooks";
import { track, AnalyticsEvent } from "@/lib/analytics/utils";
import { motion, AnimatePresence } from "motion/react";
import { NotificationType } from "@/lib/notifications/interfaces";
import { dismissNotification } from "@/lib/notifications/api";
import { AccountPopover } from "@/lib/app/components";
import { useQueryController } from "@/providers/QueryControllerProvider";
import { DEFAULT_AGENT_ID } from "@/lib/constants";

// Visible-agents = pinned-agents + current-agent (if current-agent not in pinned-agents)
// OR Visible-agents = pinned-agents (if current-agent in pinned-agents)
function buildVisibleAgents(
  pinnedAgents: MinimalAgent[],
  activeAgent: MinimalAgent | undefined
): [MinimalAgent[], boolean] {
  /* NOTE: The unified agent (id = 0) is not visible in the sidebar,
  so we filter it out. */
  if (!activeAgent)
    return [pinnedAgents.filter((agent) => agent.id !== 0), false];
  const currentAgentIsPinned = pinnedAgents.some(
    (pinnedAgent) => pinnedAgent.id === activeAgent.id
  );
  const visibleAgents = (
    currentAgentIsPinned ? pinnedAgents : [...pinnedAgents, activeAgent]
  ).filter((agent) => agent.id !== 0);

  return [visibleAgents, currentAgentIsPinned];
}

interface RecentsSectionProps {
  chatSessions: ChatSession[];
  isLoading: boolean;
  hasMore: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => void;
}

function RecentsSection({
  chatSessions,
  isLoading,
  hasMore,
  isLoadingMore,
  onLoadMore,
}: RecentsSectionProps) {
  const t = useTranslations("sidebar");
  // Sentinel ref for IntersectionObserver-based infinite scroll
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const onLoadMoreRef = useRef(onLoadMore);

  // Layout effect: an already-scheduled observer callback must not see the
  // previous page's loadMore after commit.
  useLayoutEffect(() => {
    onLoadMoreRef.current = onLoadMore;
  }, [onLoadMore]);

  useEffect(() => {
    if (!hasMore || isLoadingMore) return;

    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          onLoadMoreRef.current();
        }
      },
      { threshold: 0 }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore]);

  return (
    <SidebarLayouts.Section title={t("appSidebar.recents.title")}>
      {isLoading ? (
        <SidebarLoader count={5} />
      ) : chatSessions.length === 0 ? (
        <div className="px-3">
          <Text as="p" color="text-03">
            {t("appSidebar.recents.empty.text")}
          </Text>
        </div>
      ) : (
        <>
          {chatSessions.map((chatSession) => (
            <ChatButton
              key={chatSession.id}
              chatSession={chatSession}
            />
          ))}
          {hasMore && (
            <div
              ref={sentinelRef}
              // Waiting to scroll into view, nothing is loading yet.
              aria-hidden={!isLoadingMore}
              className={cn(
                "transition-opacity duration-300",
                isLoadingMore ? "opacity-100" : "opacity-40"
              )}
            >
              <SidebarLoader count={3} />
            </div>
          )}
        </>
      )}
    </SidebarLayouts.Section>
  );
}

export default function AppSidebar() {
  const t = useTranslations("sidebar");
  const tCraftUpgrade = useTranslations("craft.upgrade");
  const navigation = useNavigation();
  const { data: userPrefs } = useUserPreferences();
  const { data: inboxFeed } = useSWR<InboxNotificationSummary>(
    SWR_KEYS.inboxNotificationSummary,
    errorHandlingFetcher,
    { refreshInterval: 60_000 }
  );
  const { data: liveApprovals } = useSWR<{ items: unknown[] }>(
    useSettings()?.nortpole_craft_enabled === true ? SWR_KEYS.myLiveApprovals : null,
    errorHandlingFetcher,
    { refreshInterval: 15_000, shouldRetryOnError: false }
  );
  const ownWork = useOwnWork();
  const pendingProposals = usePendingProposals().waiting.length;
  const inboxCount =
    userPrefs && inboxFeed
      ? inboxBadgeCount(
          inboxFeed,
          userPrefs.notifications,
          new Date(),
          liveApprovals?.items.length ?? 0,
          ownWork.plans.length + ownWork.drafts.length + pendingProposals
        )
      : 0;
  const combinedSettingsData = useSettings();
  const { newTenantInfo, invitationInfo } = useModalContext();
  const { setAppMode, reset } = useQueryController();

  // Use SWR hooks for data fetching
  const {
    chatSessions,
    isLoading: isLoadingChatSessions,
    hasMore,
    isLoadingMore,
    loadMore,
  } = useChatSessions();
  const { isLoading: isLoadingAgents } = useAgents();
  const activeAgent = useActiveAgent();
  const {
    pinnedAgents,
    updatePinnedAgents,
    isLoading: isLoadingPinnedAgents,
  } = usePinnedAgents();

  // Each section shows its own skeleton until its own data loads.
  const isLoadingAgentList = isLoadingAgents || isLoadingPinnedAgents;

  // Check if NortPole Craft is enabled via settings (backed by PostHog feature flag)
  // Only explicit true enables the feature; false or undefined = disabled
  const isNortPoleCraftEnabled = combinedSettingsData?.nortpole_craft_enabled === true;
  const isNortPoleCraftUpsell =
    !isNortPoleCraftEnabled &&
    combinedSettingsData?.nortpole_craft_requires_upgrade === true;
  // Gated like a Business admin page: below that tier the tab is disabled.
  const hasCraftTier = useTierAtLeast(Tier.BUSINESS);
  const tTasks = useTranslations("craft.tasks");
  const unviewedTaskCount = useUnviewedScheduledTaskCount(
    isNortPoleCraftEnabled && hasCraftTier
  );
  const plans = usePlans();

  // Fetch notifications for build mode intro
  const { notifications, refresh: mutateNotifications } = useNotifications({
    enabled: isNortPoleCraftEnabled,
  });

  // Find build_mode feature announcement notification (only if NortPole Craft is enabled)
  const buildModeNotification = isNortPoleCraftEnabled
    ? notifications?.find(
        (n) =>
          n.notif_type === NotificationType.FEATURE_ANNOUNCEMENT &&
          n.additional_data?.feature === "build_mode" &&
          !n.dismissed
      )
    : undefined;

  // State for intro animation overlay
  const [showIntroAnimation, setShowIntroAnimation] = useState(false);
  // Track if auto-trigger has fired (prevents race condition during dismiss)
  const hasAutoTriggeredRef = useRef(false);

  // Auto-show intro once when there's an undismissed notification
  // Don't show if tenant/invitation modal is open (e.g., "join existing team" modal)
  // Gated by PostHog feature flag: if `craft-animation-disabled` is true (or
  // PostHog is unavailable), skip the auto-show entirely.
  const isCraftAnimationDisabled = usePHFeatureFlag(
    PHFeatureFlag.CRAFT_ANIMATION_DISABLED
  );
  const hasTenantModal = !!(newTenantInfo || invitationInfo);
  useEffect(() => {
    if (
      isNortPoleCraftEnabled &&
      buildModeNotification &&
      !hasAutoTriggeredRef.current &&
      !hasTenantModal &&
      !isCraftAnimationDisabled
    ) {
      hasAutoTriggeredRef.current = true;
      setShowIntroAnimation(true);
    }
  }, [
    buildModeNotification,
    isNortPoleCraftEnabled,
    hasTenantModal,
    isCraftAnimationDisabled,
  ]);

  // Dismiss the build mode notification
  const dismissBuildModeNotification = useCallback(async () => {
    if (!buildModeNotification) return;
    try {
      await dismissNotification(buildModeNotification.id);
      mutateNotifications();
    } catch (error) {
      console.error("Error dismissing notification:", error);
    }
  }, [buildModeNotification, mutateNotifications]);

  const [visibleAgents, currentAgentIsPinned] = useMemo(
    () => buildVisibleAgents(pinnedAgents, activeAgent),
    [pinnedAgents, activeAgent]
  );
  const visibleAgentIds = useMemo(
    () => visibleAgents.map((agent) => agent.id),
    [visibleAgents]
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Handle agent drag and drop
  const handleAgentDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over) return;
      if (active.id === over.id) return;

      const activeIndex = visibleAgentIds.findIndex(
        (agentId) => agentId === active.id
      );
      const overIndex = visibleAgentIds.findIndex(
        (agentId) => agentId === over.id
      );

      let newPinnedAgents: MinimalAgent[];

      // The Assistant is excluded: it is the active agent in plain chat but is
      // never in `visibleAgents`, so pinning it here would persist an agent the
      // sidebar cannot show.
      if (
        activeAgent &&
        activeAgent.id !== DEFAULT_AGENT_ID &&
        !currentAgentIsPinned
      ) {
        // This is the case in which the user is dragging the UNPINNED agent and moving it to somewhere else in the list.
        // This is an indication that we WANT to pin this agent!
        if (activeIndex === visibleAgentIds.length - 1) {
          const pinnedWithCurrent = [...pinnedAgents, activeAgent];
          newPinnedAgents = arrayMove(
            pinnedWithCurrent,
            activeIndex,
            overIndex
          );
        } else {
          // Use visibleAgents to ensure the indices match with `visibleAgentIds`
          newPinnedAgents = arrayMove(visibleAgents, activeIndex, overIndex);
        }
      } else {
        // Use visibleAgents to ensure the indices match with `visibleAgentIds`
        newPinnedAgents = arrayMove(visibleAgents, activeIndex, overIndex);
      }

      updatePinnedAgents(newPinnedAgents);
    },
    [
      visibleAgentIds,
      visibleAgents,
      pinnedAgents,
      updatePinnedAgents,
      activeAgent,
      currentAgentIsPinned,
    ]
  );

  const { hasAdminAccess, adminCapabilities, user, isAdmin } = useUser();
  const activeSidebarTab = useAppPosition();
  const craftLink = navigation.linkTo(CRAFT_PATH, { scroll: false });
  const defaultAppMode =
    (user?.preferences?.default_app_mode?.toLowerCase() as "chat" | "search") ??
    "chat";

  const handleShowBuildIntro = useCallback(() => {
    setShowIntroAnimation(true);
  }, []);

  return (
    <>
      {/* Intro animation overlay */}
      <AnimatePresence>
        {showIntroAnimation && (
          <motion.div
            className="fixed inset-0 z-9999"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
          >
            <BuildModeIntroBackground />
            <BuildModeIntroContent
              onClose={() => {
                setShowIntroAnimation(false);
                dismissBuildModeNotification();
              }}
              onTryBuildMode={() => {
                setShowIntroAnimation(false);
                dismissBuildModeNotification();
                navigation.go(CRAFT_PATH);
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <SidebarLayouts.Root foldable>
        <BrandedSidebarHeader>
          <div data-testid="AppSidebar/new-session">
            <SidebarTab
              icon={SvgEditBig}
              href={activeSidebarTab.linkToNewSession().href}
              selected={activeSidebarTab.isNewSession()}
              onClick={(event) => {
                // Already on a new session: start it over instead.
                if (activeSidebarTab.isNewSession()) {
                  setAppMode(defaultAppMode);
                  reset();
                  return;
                }
                activeSidebarTab.linkToNewSession().onClick(event);
              }}
            >
              {t("appSidebar.newSession.label")}
            </SidebarTab>
          </div>
          <SidebarTab
            icon={SvgSearchMenu}
            {...navigation.linkTo("/app/search", { scroll: false })}
            selected={activeSidebarTab.isSearch()}
          >
            {t("appSidebar.searchChats.label")}
          </SidebarTab>
          <SidebarTab
            icon={SvgBell}
            {...navigation.linkTo("/app/inbox", { scroll: false })}
            selected={activeSidebarTab.isInbox()}
            rightChildren={
              inboxCount > 0 ? (
                <span
                  data-testid="inbox-badge"
                  aria-label={`${inboxCount} in your inbox`}
                  className="min-w-5 rounded-full bg-text-05 px-1.5 text-center text-xs font-semibold leading-5 text-background-neutral-00"
                >
                  {inboxCount > 99 ? "99+" : inboxCount}
                </span>
              ) : undefined
            }
          >
            {t("appSidebar.inbox.label")}
          </SidebarTab>
          <SidebarTab
            icon={SvgNortPoleOctagon}
            {...navigation.linkTo("/app/agents", { scroll: false })}
            selected={activeSidebarTab.isAgents()}
          >
            {t("appSidebar.agents.title")}
          </SidebarTab>
          <SidebarTab
            icon={SvgStackLine}
            {...navigation.linkTo("/app/workflows", { scroll: false })}
            selected={activeSidebarTab.isWorkflows()}
          >
            {t("appSidebar.workflows.label")}
          </SidebarTab>
          <SidebarTab
            icon={SvgFolder}
            {...navigation.linkTo("/app/projects", { scroll: false })}
            selected={activeSidebarTab.isProjects()}
          >
            {t("appSidebar.projects.title")}
          </SidebarTab>
          <SidebarTab
            icon={SvgFiles}
            {...navigation.linkTo("/app/knowledge", { scroll: false })}
            selected={activeSidebarTab.isKnowledge()}
          >
            {t("appSidebar.knowledge.label")}
          </SidebarTab>
          <SidebarTab
            icon={SvgPlug}
            {...navigation.linkTo("/app/sources/integrations", { scroll: false })}
            selected={activeSidebarTab.isSources()}
          >
            {t("appSidebar.sources.label")}
          </SidebarTab>
          {(isNortPoleCraftEnabled || isNortPoleCraftUpsell) && (
            <div data-testid="AppSidebar/build">
              <Disabled
                disabled={!hasCraftTier}
                // Only admins can open billing, so others are told to ask one.
                tooltip={
                  isAdmin
                    ? plans[Tier.BUSINESS].tooltip
                    : tCraftUpgrade("userDescription")
                }
              >
                <SidebarTab
                  icon={SvgDevKit}
                  href={hasCraftTier ? craftLink.href : undefined}
                  onClick={
                    hasCraftTier
                      ? (event) => {
                          track(AnalyticsEvent.CLICKED_CRAFT_IN_SIDEBAR);
                          craftLink.onClick(event);
                        }
                      : undefined
                  }
                  rightChildren={
                    isNortPoleCraftUpsell ? (
                      <PlanTag plan={Tier.BUSINESS} />
                    ) : (
                      <Section
                        flexDirection="row"
                        gap={1.5}
                        width="fit"
                        height="fit"
                      >
                        {unviewedTaskCount > 0 && (
                          <UnseenMarker label={tTasks("unviewedResults")} />
                        )}
                        <BetaTag />
                      </Section>
                    )
                  }
                >
                  {t("appSidebar.craft.label")}
                </SidebarTab>
              </Disabled>
            </div>
          )}
        </BrandedSidebarHeader>

        <SidebarLayouts.Body scrollKey="app-sidebar">
          <>
            {(isLoadingAgentList || visibleAgents.length > 0) && (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleAgentDragEnd}
              >
                <SidebarLayouts.Section>
                  <SortableContext
                    items={visibleAgentIds}
                    strategy={verticalListSortingStrategy}
                  >
                    {isLoadingAgentList ? (
                      <SidebarLoader count={3} />
                    ) : (
                      visibleAgents.map((visibleAgent) => (
                        <AgentButton key={visibleAgent.id} agent={visibleAgent} />
                      ))
                    )}
                  </SortableContext>
                </SidebarLayouts.Section>
              </DndContext>
            )}

            <RecentsSection
              chatSessions={chatSessions}
              isLoading={isLoadingChatSessions}
              hasMore={hasMore}
              isLoadingMore={isLoadingMore}
              onLoadMore={loadMore}
            />
          </>
        </SidebarLayouts.Body>

        <SidebarLayouts.Footer>
          <div>
            {hasAdminAccess && (
              <SidebarTab
                {...navigation.linkTo(
                  // SAFETY: the first permitted admin route is a page of this app.
                  getFirstPermittedAdminRoute(adminCapabilities) as Route,
                  { scroll: false }
                )}
                icon={SvgSettings}
              >
                {t("appSidebar.adminPanel.label")}
              </SidebarTab>
            )}
            <AccountPopover
              onShowBuildIntro={
                isNortPoleCraftEnabled ? handleShowBuildIntro : undefined
              }
            />
          </div>
        </SidebarLayouts.Footer>
      </SidebarLayouts.Root>
    </>
  );
}
