"use client";

import { useNavigation } from "@opal/navigation";
import { createContext, useCallback, useContext, useMemo } from "react";
import { useTranslations } from "next-intl";
import { MinimalAgent } from "@/lib/agents/types";
import AgentAvatar from "@/refresh-components/avatars/AgentAvatar";
import { Button, SelectCard, Text, useCreateModal } from "@opal/components";
import { usePinnedAgents } from "@/lib/agents/hooks";
import { noProp } from "@/lib/utils";
import { can } from "@/lib/permissions/resource-actions";
import { useTierAtLeast } from "@/lib/tiers/hooks";
import { Tier } from "@/lib/tiers/types";
import {
  SvgActions,
  SvgBarChart,
  SvgBubbleText,
  SvgEdit,
  SvgStar,
  SvgShare,
} from "@opal/icons";
import { useAppPosition } from "@/lib/navigation/hooks";
import { ShareAgentModal } from "@/lib/agents/components/ShareAgentModal";
import { Content, ContentAction, Section, toast } from "@opal/layouts";
import { Hoverable } from "@opal/core";
import { cn } from "@opal/utils";
import type { IconProps } from "@opal/types";

export interface AgentCardProps {
  agent: MinimalAgent;
  /** Opens this agent's viewer, which the listing renders. */
  onView: () => void;
  /** This agent's viewer is open: the card keeps its focused look under it. */
  viewing?: boolean;
}

// Whether the pin icon below shows the pinned pose. A context, so the icon
// stays one component across both states and its rotation can animate: a
// component per state would remount on every toggle.
const PinnedContext = createContext(false);

/** A star that fills when the agent is starred (pinned). */
function StarIcon({ className, ...props }: IconProps) {
  const pinned = useContext(PinnedContext);
  return (
    <SvgStar
      {...props}
      className={cn(
        className,
        "transition-colors duration-200 motion-reduce:transition-none",
        pinned && "fill-current",
      )}
    />
  );
}

export function AgentCard({ agent, onView, viewing = false }: AgentCardProps) {
  const t = useTranslations("agents");
  const appPosition = useAppPosition();
  const navigation = useNavigation();
  const { pinnedAgents, togglePinnedAgent } = usePinnedAgents();
  const pinned = useMemo(
    () => pinnedAgents.some((pinnedAgent) => pinnedAgent.id === agent.id),
    [agent.id, pinnedAgents],
  );
  const businessTier = useTierAtLeast(Tier.BUSINESS);
  const shareAgentModal = useCreateModal();

  // A failed pin write reverts the pin; say so rather than fail silently.
  const setPinned = useCallback(
    async (next: boolean) => {
      try {
        await togglePinnedAgent(agent, next);
      } catch {
        toast.error(t("card.pinFailed.message"));
      }
    },
    [togglePinnedAgent, agent, t],
  );

  // Start chat and auto-pin unpinned agents to the sidebar
  const handleStartChat = useCallback(() => {
    if (!pinned) void setPinned(true);
    appPosition.openAgent(agent.id);
  }, [pinned, setPinned, agent, appPosition]);

  const pinButton = (
    <PinnedContext.Provider value={pinned}>
      <Button
        icon={StarIcon}
        prominence="tertiary"
        size="md"
        onClick={noProp(() => void setPinned(!pinned))}
        tooltip={pinned ? t("card.unpin.tooltip") : t("card.pin.tooltip")}
      />
    </PinnedContext.Provider>
  );

  return (
    <>
      <shareAgentModal.Provider>
        {/* Saved agents persist sharing inside the dialog itself */}
        <ShareAgentModal agentId={agent.id} />
      </shareAgentModal.Provider>

      <SelectCard
        state="filled"
        padding={0}
        onClick={onView}
        interaction={viewing ? "hover" : undefined}
        // Lets the catalog's arrow keys find the cards.
        data-agent-card=""
      >
        <Hoverable.Root group="AgentCard" height="full">
          {/* The card has a fixed height; the footer sits at its bottom. */}
          <Section
            justifyContent="between"
            alignItems="stretch"
            gap={0}
            className="relative"
          >
            <Section gap={1} padding={1} alignItems="stretch" height="fit">
              <ContentAction
                font="main-content-emphasis"
                icon={(props) => <AgentAvatar agent={agent} {...props} />}
                title={agent.name}
                description={`${t("card.by.label")} ${
                  agent.owner?.email?.split("@")[0] || "NortPole"
                }`}
                titleMaxLines={1}
                padding={1.5}
              />
              <Section
                className="absolute right-1 top-1"
                flexDirection="row"
                width="fit"
                height="fit"
                gap={0}
                padding={1}
              >
                {/* Edit and share float over the title on hover, so the
                        title keeps the full width at rest. */}
                <div className="absolute right-11 top-2 flex flex-row rounded-08">
                  {can(agent, "edit") && (
                    <Hoverable.Item group="AgentCard">
                      <Button
                        icon={SvgEdit}
                        prominence="tertiary"
                        size="md"
                        onClick={noProp(() =>
                          navigation.go(`/app/agents/edit/${agent.id}`),
                        )}
                        tooltip={t("card.edit.tooltip")}
                      />
                    </Hoverable.Item>
                  )}
                  {can(agent, "share") && (
                    <Hoverable.Item group="AgentCard">
                      <Button
                        icon={SvgShare}
                        prominence="tertiary"
                        size="md"
                        onClick={noProp(() => shareAgentModal.toggle(true))}
                        tooltip={t("card.share.tooltip")}
                      />
                    </Hoverable.Item>
                  )}
                </div>
                {/* A pinned agent shows its pin at rest; an unpinned one only
                        offers the action on hover. One wrapper either way, so the pin
                        keeps its element and its rotation animates. */}
                <Hoverable.Item group="AgentCard" revealed={pinned}>
                  {pinButton}
                </Hoverable.Item>
              </Section>
              {agent.description && (
                <div className="px-2">
                  <Text
                    as="p"
                    font="secondary-body"
                    color="text-03"
                    maxLines={2}
                  >
                    {agent.description}
                  </Text>
                </div>
              )}
            </Section>

            {/* Footer section - bg-background-tint-01 */}
            <Section
              flexDirection="row"
              justifyContent="between"
              alignItems="end"
              height="fit"
              gap={1}
              padding={1}
              className="bg-background-tint-01"
            >
              {/* Left side - creator and actions. Section pads evenly, so
                  the uneven padding sits on a plain wrapper. */}
              <div className="px-2 py-1">
                <Section alignItems="stretch" width="auto" height="fit" gap={1}>
                  <Content
                    font="secondary-body"
                    icon={SvgActions}
                    title={t("card.actionsCount.label", {
                      count: agent.tools.length,
                    })}
                    titleColor="text-03"
                  />
                </Section>
              </div>

              {/* Right side - Start Chat button */}
              <Button
                prominence="tertiary"
                rightIcon={SvgBubbleText}
                onClick={noProp(handleStartChat)}
              >
                {t("card.startChat.label")}
              </Button>
            </Section>
          </Section>
        </Hoverable.Root>
      </SelectCard>
    </>
  );
}
