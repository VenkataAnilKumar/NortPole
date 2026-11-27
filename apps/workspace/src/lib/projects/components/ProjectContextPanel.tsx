"use client";

import { loadPage } from "@opal/navigation";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { IconLoader } from "@opal/loaders";
import React, { useCallback } from "react";
import { useTranslations } from "next-intl";
import { useDropzone } from "react-dropzone";
import { useProjectsContext } from "@/lib/projects/providers";
import FilePickerPopover from "@/refresh-components/popovers/FilePickerPopover";
import { UserFileStatus, type ProjectFile } from "@/lib/projects/types";
import { MinimalNortPoleDocument } from "@/lib/search/types";
import { Button, Divider, LineItemButton, Text } from "@opal/components";
import { Content, ContentAction } from "@opal/layouts";
import AddInstructionModal from "@/sections/modals/AddInstructionModal";
import UserFilesModal from "@/sections/modals/UserFilesModal";
import { useCreateModal } from "@opal/components";
import { FileCard } from "@/sections/cards/FileCard";
import { hasNonImageFiles } from "@/lib/utils";
import { cn } from "@opal/utils";
import ProjectOutputs from "./ProjectOutputs";
import { ProjectSharing } from "./ProjectSharing";
import {
  SvgAddLines,
  SvgFiles,
  SvgFolderOpen,
  SvgPlusCircle,
} from "@opal/icons";

export interface ProjectContextPanelProps {
  projectTokenCount?: number;
  availableContextTokens?: number;
  setPresentingDocument?: (document: MinimalNortPoleDocument) => void;
}

export default function ProjectContextPanel({
  projectTokenCount = 0,
  availableContextTokens = 128_000,
  setPresentingDocument,
}: ProjectContextPanelProps) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const t = useTranslations("chat");
  const addInstructionModal = useCreateModal();
  const projectFilesModal = useCreateModal();
  const {
    currentProjectDetails,
    currentProjectId,
    unlinkFileFromProject,
    linkFileToProject,
    allCurrentProjectFiles,
    isLoadingProjectDetails,
    beginUpload,
    projects,
    renameProject,
  } = useProjectsContext();
  const currentProject = projects.find((project) => project.id === currentProjectId);
  const canEdit = !!currentProject && currentProject.role !== "viewer";
  const shared = currentProject?.shared === true;
  const projectOwnerId = currentProject?.user_id;
  const handleOnView = useCallback(
    (file: ProjectFile) => {
      if ((shared || file.user_id !== projectOwnerId) && currentProjectId && file.status !== UserFileStatus.UPLOADING) {
        loadPage(`/api/user/projects/${currentProjectId}/files/${encodeURIComponent(file.id)}/download`);
        return;
      }
      setPresentingDocument?.({
        document_id: `project_file__${file.file_id}`,
        semantic_identifier: file.name,
      });
    },
    [currentProjectId, projectOwnerId, setPresentingDocument, shared]
  );
  const handleUploadFiles = useCallback(
    async (files: File[]) => {
      if (!canEdit || !files || files.length === 0) return;
      beginUpload(Array.from(files), currentProjectId);
    },
    [canEdit, currentProjectId, beginUpload]
  );

  const totalFiles = allCurrentProjectFiles.length;
  const fileCountLabel =
    totalFiles > 100
      ? t("projects.contextPanel.fileCountOverflow.description")
      : t("projects.contextPanel.fileCount.description", {
          count: totalFiles,
        });

  const handleUploadChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;
      await handleUploadFiles(Array.from(files));
      e.target.value = "";
    },
    [handleUploadFiles]
  );

  // Nested dropzone for drag-and-drop within ProjectContextPanel
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    disabled: !canEdit,
    noClick: true,
    noKeyboard: true,
    multiple: true,
    noDragEventsBubbling: true,
    onDrop: (acceptedFiles) => {
      void handleUploadFiles(acceptedFiles);
    },
  });

  const projectName =
    currentProject?.name || t("projects.contextPanel.loadingProject.label");

  if (!currentProjectId) return null;
  if (isLoadingProjectDetails && !currentProjectDetails) return <IconLoader />;
  if (!currentProject || !currentProjectDetails) {
    return <p role="alert" className="mx-auto p-6 text-text-05">{workspaceText("thisProjectIsUnavailable")}</p>;
  }

  // Detect if there are any non-image files in the displayed files
  // to determine if images should be compact
  const displayedFiles = allCurrentProjectFiles.slice(0, 4);
  const shouldCompactImages = hasNonImageFiles(displayedFiles);

  return (
    <>
      <addInstructionModal.Provider>
        <AddInstructionModal />
      </addInstructionModal.Provider>

      <projectFilesModal.Provider>
        <UserFilesModal
          title={t("projects.contextPanel.filesModal.title")}
          description={t("projects.contextPanel.filesModal.description")}
          recentFiles={[...allCurrentProjectFiles]}
          onView={handleOnView}
          handleUploadChange={canEdit ? handleUploadChange : undefined}
          onDelete={canEdit ? async (file: ProjectFile) => {
            if (!currentProjectId) return;
            await unlinkFileFromProject(currentProjectId, file.id);
          } : undefined}
        />
      </projectFilesModal.Provider>

      <div className="w-(--app-page-main-content-width) mx-auto flex flex-col gap-6 pb-6">
        <Content
          font="heading-headline"
          orientation="stacked"
          icon={SvgFolderOpen}
          title={projectName}
          editable={canEdit}
          onTitleChange={async (newName) => {
            if (currentProjectId && newName) {
              await renameProject(currentProjectId, newName);
            }
          }}
        />

        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-text-03">
            {shared ? "Shared project" : "Private project"}
            {currentProject.role === "viewer" && " · Viewer"}
            {currentProject.role === "editor" && " · Editor"}
          </p>
          <ProjectSharing key={currentProject.id} project={currentProject} />
        </div>

        <Divider paddingParallel={0} paddingPerpendicular={0} />

        <ContentAction
          font="main-ui-action"
          title={t("projects.contextPanel.instructions.title")}
          description={
            isLoadingProjectDetails && !currentProjectDetails
              ? undefined
              : currentProjectDetails?.project?.instructions ||
                t("projects.contextPanel.instructions.emptyDescription")
          }
          descriptionMaxLines={2}
          padding={0}
          center
          rightChildren={canEdit && (
            <Button
              prominence="tertiary"
              icon={SvgAddLines}
              onClick={() => addInstructionModal.toggle(true)}
              interaction={addInstructionModal.isOpen ? "active" : undefined}
            >
              {t("projects.contextPanel.setInstructionsButton.label")}
            </Button>
          )}
        />

        <ProjectOutputs key={currentProjectId} projectId={currentProjectId} canEdit={canEdit} />

        <div
          className="flex flex-col gap-2 pb-2"
          {...getRootProps({ onClick: (e) => e.stopPropagation() })}
        >
          <ContentAction
            font="main-ui-action"
            title={t("projects.contextPanel.files.title")}
            description={t("projects.contextPanel.files.description")}
            padding={0}
            center
            rightChildren={canEdit && (
              <FilePickerPopover
                trigger={(open) => (
                  <Button
                    icon={SvgPlusCircle}
                    prominence="tertiary"
                    interaction={open ? "active" : undefined}
                  >
                    {t("projects.contextPanel.addFilesButton.label")}
                  </Button>
                )}
                onFileClick={handleOnView}
                onPickRecent={async (file) => {
                  if (file.status === UserFileStatus.UPLOADING) return;
                  if (file.status === UserFileStatus.DELETING) return;
                  if (!currentProjectId) return;
                  if (!linkFileToProject) return;
                  linkFileToProject(currentProjectId, file);
                }}
                onUnpickRecent={async (file) => {
                  if (!currentProjectId) return;
                  await unlinkFileFromProject(currentProjectId, file.id);
                }}
                handleUploadChange={handleUploadChange}
                selectedFileIds={(allCurrentProjectFiles || []).map(
                  (f) => f.id
                )}
              />
            )}
          />

          {/* Hidden input just to satisfy dropzone contract; we rely on FilePicker for clicks */}
          <input {...getInputProps()} />

          {allCurrentProjectFiles.length > 0 ? (
            <>
              {/* Mobile / small screens: just show a button to view files */}
              <div className="sm:hidden">
                <LineItemButton
                  font="main-ui-action"
                  title={t("projects.contextPanel.viewFiles.label")}
                  description={fileCountLabel}
                  icon={SvgFiles}
                  width="full"
                  onClick={() => projectFilesModal.toggle(true)}
                />
              </div>

              {/* Desktop / larger screens: show previews with optional View All */}
              <div className="hidden sm:flex gap-1 relative items-center">
                {allCurrentProjectFiles.slice(0, 4).map((f) => (
                  <FileCard
                    key={f.id}
                    file={f}
                    removeFile={canEdit ? async (fileId: string) => {
                      if (!currentProjectId) return;
                      await unlinkFileFromProject(currentProjectId, fileId);
                    } : undefined}
                    onFileClick={handleOnView}
                    compactImages={shouldCompactImages}
                    showImagePreview={!shared && f.user_id === projectOwnerId}
                  />
                ))}

                {totalFiles > 4 && (
                  <LineItemButton
                    font="main-ui-action"
                    title={t("projects.contextPanel.viewAll.label")}
                    description={fileCountLabel}
                    rightChildren={
                      <SvgFiles className="h-5 w-5 stroke-text-02" />
                    }
                    onClick={() => projectFilesModal.toggle(true)}
                  />
                )}
                {isDragActive && (
                  <div className="pointer-events-none absolute inset-0 rounded-lg border-2 border-dashed border-action-selection-05" />
                )}
              </div>

              {projectTokenCount > availableContextTokens && (
                <Text as="p" font="secondary-body" color="text-02">
                  {t("projects.contextPanel.contextExceeded.message")}
                </Text>
              )}
            </>
          ) : (
            <div
              className={cn(
                "h-12 rounded-xl border border-dashed flex items-center ps-2",
                isDragActive
                  ? "bg-action-selection-01 border-action-selection-05 text-action-selection-05"
                  : "border-border-01 text-text-02"
              )}
            >
              <Text as="p" font="secondary-body" color="inherit">
                {isDragActive
                  ? t("projects.contextPanel.dropFiles.message")
                  : canEdit ? t("projects.contextPanel.emptyFiles.message") : "No project files"}
              </Text>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
