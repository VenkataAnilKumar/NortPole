"use client";

import React, { useState, memo, useMemo, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useDraggable } from "@dnd-kit/core";
import useChatSessions from "@/hooks/useChatSessions";
import { deleteChatSession, renameChatSession } from "@/app/app/services/lib";
import { ChatSession } from "@/app/app/types";
import { ConfirmationModalLayout } from "@opal/layouts";
import { noProp } from "@/lib/utils";
import {
  Dropdown,
  type DropdownMenuItem,
  type DropdownView,
} from "@opal/components";
import type { Project } from "@/lib/projects/types";
import {
  removeChatSessionFromProject,
  createProject as createProjectService,
} from "@/lib/projects/svc";
import { useProjectsContext } from "@/lib/projects/providers";
import { MoveProjectChatModal } from "@/lib/projects/components/MoveProjectChatModal";
import { UNNAMED_CHAT } from "@/lib/constants";
import ShareChatSessionModal from "@/sections/modals/ShareChatSessionModal";
import { Button, SidebarTab, useCreateModal } from "@opal/components";
import { Hoverable } from "@opal/core";
import { DRAG_TYPES } from "@/lib/sidebar/constants";
import { showErrorNotification } from "@/lib/sidebar/utils";
import { handleMoveOperation } from "@/lib/sidebar/svc";
import ButtonRenaming from "@/refresh-components/buttons/ButtonRenaming";
import { useAppPosition } from "@/lib/navigation/hooks";
import {
  SvgChevronLeft,
  SvgEdit,
  SvgFolder,
  SvgFolderIn,
  SvgFolderPlus,
  SvgMoreHorizontal,
  SvgShare,
  SvgTrash,
} from "@opal/icons";
import useOnMount from "@/hooks/useOnMount";
import { usePinChatAgent } from "@/lib/agents/hooks";

export interface ChatButtonProps {
  chatSession: ChatSession;
  project?: Project;
  draggable?: boolean;
}

const ChatButton = memo(
  ({ chatSession, project, draggable = false }: ChatButtonProps) => {
    const t = useTranslations("sidebar");
    const appPosition = useAppPosition();
    const active = useMemo(
      () => appPosition.isChat() && appPosition.chat() === chatSession.id,
      [appPosition, chatSession.id]
    );
    const mounted = useOnMount();
    const [displayName, setDisplayName] = useState(
      chatSession.name || UNNAMED_CHAT
    );
    const [renaming, setRenaming] = useState(false);
    const deleteModal = useCreateModal();
    const shareModal = useCreateModal();
    const [searchTerm, setSearchTerm] = useState("");
    const { refreshChatSessions, removeSession } = useChatSessions();
    const {
      refreshCurrentProjectDetails,
      projects,
      fetchProjects,
      currentProjectId,
    } = useProjectsContext();
    const pinChatAgent = usePinChatAgent();
    const [menuOpen, setMenuOpen] = useState(false);
    const [pendingMove, setPendingMove] = useState<{
      id?: number;
      name: string;
      shared?: boolean;
    } | null>(null);
    const moveProjectChatModal = useCreateModal();

    // Drag and drop setup for chat sessions
    const dragId = `${DRAG_TYPES.CHAT}-${chatSession.id}`;
    // `attributes` is intentionally dropped: it turns the wrapper into a
    // focusable role="button", which adds a second tab stop per row and lets
    // Enter/Space start a keyboard drag that looks like the chat is disabled.
    const { listeners, setNodeRef, transform, isDragging } = useDraggable({
      id: dragId,
      data: {
        type: DRAG_TYPES.CHAT,
        chatSession,
        projectId: project?.id,
      },
      disabled: !draggable || renaming || Boolean(chatSession.agent_preview_name),
    });

    // Sync local name state when chatSession.name changes (e.g., after auto-naming)
    useEffect(() => {
      const newName = chatSession.name || UNNAMED_CHAT;
      const oldName = displayName;

      // Only animate if transitioning from UNNAMED_CHAT to a real name
      if (oldName === UNNAMED_CHAT && newName !== UNNAMED_CHAT && mounted) {
        // Type out the name character by character
        let currentIndex = 0;
        const typingInterval = setInterval(() => {
          currentIndex++;
          setDisplayName(newName.slice(0, currentIndex));

          if (currentIndex >= newName.length) {
            clearInterval(typingInterval);
          }
        }, 30); // 30ms per character

        return () => clearInterval(typingInterval);
      } else {
        // No animation for other changes (manual rename, initial load, etc.)
        setDisplayName(newName);
      }
    }, [chatSession.name, mounted]);

    const filteredProjects = useMemo(() => {
      // Trimmed, as the list's own filter trims it.
      const term = searchTerm.trim().toLowerCase();
      return projects.filter((project) =>
        project.role !== "viewer" && project.name.toLowerCase().includes(term)
      );
    }, [projects, searchTerm]);

    const availableProjects = filteredProjects.filter(
      (candidateProject) => candidateProject.id !== project?.id
    );
    // The move page: the view's own search filters the projects; the way
    // back and the create row stay pinned above the filter.
    const moveView: DropdownView = {
      search: {
        placeholder: t("chatButton.projectSearchInput.placeholder"),
        onChange: setSearchTerm,
      },
      items: [
        {
          kind: "action",
          id: "back",
          pinned: true,
          icon: SvgChevronLeft,
          title: t("chatButton.moveToProject.label"),
          onSelect: (views) => views.pop(),
        },
        ...projects
          .filter((candidateProject) => candidateProject.id !== project?.id)
          .map(
            (targetProject): DropdownMenuItem => ({
              kind: "action",
              id: `project-${targetProject.id}`,
              icon: SvgFolder,
              title: targetProject.name,
              onSelect: () => confirmChatMove(targetProject),
            })
          ),
        // A create row when no project matches the search.
        ...(availableProjects.length === 0 && searchTerm.trim() !== ""
          ? [
              {
                kind: "group" as const,
                items: [
                  {
                    kind: "action" as const,
                    id: "create-new",
                    pinned: true,
                    icon: SvgFolderPlus,
                    title: t("chatButton.createProject.label", {
                      projectName: searchTerm.trim(),
                    }),
                    onSelect: () =>
                      confirmChatMove({ name: searchTerm.trim() }),
                  },
                ],
              },
            ]
          : []),
      ],
    };
    const menuItems: DropdownMenuItem[] = [
      ...(project?.shared || chatSession.agent_preview_name ? [] : [{
        kind: "action" as const,
        id: "share",
        icon: SvgShare,
        title: t("chatButton.share.label"),
        onSelect: () => shareModal.toggle(true),
      }]),
      {
        kind: "action",
        id: "rename",
        icon: SvgEdit,
        title: t("chatButton.rename.label"),
        onSelect: () => setRenaming(true),
      },
      ...(chatSession.agent_preview_name ? [] : [{
        kind: "action" as const,
        id: "move",
        icon: SvgFolderIn,
        title: t("chatButton.moveToProject.label"),
        onSelect: (views) => views.push("move"),
      }] satisfies DropdownMenuItem[]),
      ...(project
        ? [
            {
              kind: "action" as const,
              id: "remove",
              icon: SvgFolder,
              title: t("chatButton.removeFromProject.label", {
                projectName: project.name,
              }),
              onSelect: () => handleRemoveFromProject(),
            },
          ]
        : []),
      {
        kind: "group",
        items: [
          {
            kind: "action",
            id: "delete",
            icon: SvgTrash,
            danger: true,
            title: t("chatButton.delete.label"),
            onSelect: () => deleteModal.toggle(true),
          },
        ],
      },
    ];

    // Pin the chat's agent when clicking on the conversation
    const chatLink = appPosition.linkToChat(chatSession.id);

    async function handleClick(event: React.MouseEvent<HTMLElement>) {
      chatLink.onClick(event);
      if (!chatSession.agent_preview_name) await pinChatAgent(chatSession);
    }

    async function handleRename(newName: string) {
      setDisplayName(newName);
      await renameChatSession(chatSession.id, newName);
      await refreshChatSessions();
    }

    async function handleChatDelete() {
      try {
        await deleteChatSession(chatSession.id);
        removeSession(chatSession.id);

        if (project) {
          await fetchProjects();
          await refreshCurrentProjectDetails();

          // Only route if the deleted chat is the currently opened chat session
          if (appPosition.chat() === chatSession.id) {
            appPosition.openProject(project.id);
          }
        }
        await refreshChatSessions();
      } catch (error) {
        console.error("Failed to delete chat:", error);
        showErrorNotification(t("chatButton.deleteError.message"));
      }
    }

    function confirmChatMove(target: { id?: number; name: string; shared?: boolean }) {
      setPendingMove(target);
      moveProjectChatModal.toggle(true);
    }

    function closeMove() {
      moveProjectChatModal.toggle(false);
      setPendingMove(null);
    }

    async function performMove(target: { id?: number; name: string }) {
      if (target.id === undefined) {
        let newProject: Project;
        try {
          newProject = await createProjectService(target.name, chatSession.id);
        } catch {
          showErrorNotification(t("chatButton.createProjectError.message"));
          return;
        }
        setSearchTerm("");
        appPosition.openProject(newProject.id);
        await Promise.allSettled([refreshChatSessions(), fetchProjects()]);
        return;
      }

      try {
        await handleMoveOperation({
          chatSession,
          targetProjectId: target.id,
          refreshChatSessions,
          refreshCurrentProjectDetails,
          fetchProjects,
          currentProjectId,
        });
        setSearchTerm("");
      } catch {
        // The move service already reports a failure.
      }
    }

    async function handleRemoveFromProject() {
      try {
        await removeChatSessionFromProject(chatSession.id);
        const projectRefreshPromise = currentProjectId
          ? refreshCurrentProjectDetails()
          : fetchProjects();
        await Promise.all([refreshChatSessions(), projectRefreshPromise]);
        setSearchTerm("");
      } catch (error) {
        console.error("Failed to remove chat from project:", error);
      }
    }

    const rightMenu = (
      <>
        {/* The click stays here: the row underneath opens the chat. */}
        <div
          role="presentation"
          data-testid="ChatButton/options"
          onClick={noProp()}
        >
          {/* While renaming the row is an input, so the menu stays away unless
              its own list is already open. */}
          {(!renaming || menuOpen) && (
            <Hoverable.Item group="ChatButton">
              <Dropdown.Trigger asChild>
                <Button
                  icon={SvgMoreHorizontal}
                  prominence="internal"
                  size="sm"
                  interaction={menuOpen ? "hover" : "rest"}
                  aria-label={t("chatButton.options.label")}
                />
              </Dropdown.Trigger>
            </Hoverable.Item>
          )}
        </div>
        <Dropdown.Data
          label={t("chatButton.options.label")}
          items={menuItems}
          views={{ move: moveView }}
        />
      </>
    );

    const popover = (
      <Dropdown width={60} side="right" onOpenChange={setMenuOpen}>
        <Hoverable.Root
          group="ChatButton"
          data-testid="ChatButton"
          interaction={menuOpen ? "hover" : "rest"}
        >
          <SidebarTab
            /* While renaming, drop the click target so the input stays usable. */
            href={isDragging || renaming ? undefined : chatLink.href}
            onClick={renaming ? undefined : handleClick}
            selected={active}
            rightChildren={rightMenu}
            nested={!!project}
          >
            {renaming ? (
              <ButtonRenaming
                initialName={chatSession.name}
                onRename={handleRename}
                onClose={() => setRenaming(false)}
              />
            ) : (
              displayName
            )}
          </SidebarTab>
        </Hoverable.Root>
      </Dropdown>
    );

    return (
      <>
        <deleteModal.Provider>
          <ConfirmationModalLayout
            title={t("chatButton.deleteConfirmation.title")}
            icon={SvgTrash}
            onClose={() => deleteModal.toggle(false)}
            submit={
              <Button
                variant="danger"
                onClick={() => {
                  deleteModal.toggle(false);
                  handleChatDelete();
                }}
              >
                {t("chatButton.deleteConfirmation.confirmButton.label")}
              </Button>
            }
          >
            {t("chatButton.deleteConfirmation.description")}
          </ConfirmationModalLayout>
        </deleteModal.Provider>

        <moveProjectChatModal.Provider>
          {pendingMove && (
            <MoveProjectChatModal
              projectName={pendingMove.name}
              shared={pendingMove.shared}
              createProject={pendingMove.id === undefined}
              onCancel={closeMove}
              onConfirm={() => {
                closeMove();
                void performMove(pendingMove);
              }}
            />
          )}
        </moveProjectChatModal.Provider>

        <shareModal.Provider>
          <ShareChatSessionModal
            chatSession={chatSession}
            onClose={() => shareModal.toggle(false)}
          />
        </shareModal.Provider>

        {draggable ? (
          <div
            ref={setNodeRef}
            style={{
              transform: transform
                ? `translate3d(0px, ${transform.y}px, 0)`
                : undefined,
              opacity: isDragging ? 0.5 : 1,
            }}
            {...(mounted ? listeners : {})}
          >
            {popover}
          </div>
        ) : (
          popover
        )}
      </>
    );
  }
);
ChatButton.displayName = "ChatButton";

export default ChatButton;
