"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button, NativeInput, useCreateModal } from "@opal/components";
import { SvgFolder, SvgFolderPlus, SvgTrash } from "@opal/icons";
import { ConfirmationModalLayout, ResponsiveLayout, SettingsLayouts, toast } from "@opal/layouts";
import { NavLink } from "@opal/navigation";
import { useAppPosition } from "@/lib/navigation/hooks";
import { CreateProjectModal } from "@/lib/projects/components";
import { useProjects } from "@/lib/projects/hooks";
import { useProjectsContext } from "@/lib/projects/providers";
import type { Project } from "@/lib/projects/types";

export default function ProjectsPage() {
  const sidebar = useTranslations("sidebar.appSidebar");
  const copy = useTranslations("chat.composerContext");
  const projectCopy = useTranslations("chat.projects.folder");
  const workspace = useTranslations("workspaceUi");
  const appPosition = useAppPosition();
  const createModal = useCreateModal();
  const deleteModal = useCreateModal();
  const { projects, isLoading, error, refreshProjects } = useProjects();
  const { deleteProject } = useProjectsContext();
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [query, setQuery] = useState("");
  const search = query.trim().toLowerCase();
  const visible = projects.filter((project) =>
    [project.name, project.description].some((text) =>
      text?.toLowerCase().includes(search),
    ),
  );

  async function confirmDelete() {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await deleteProject(deleteTarget.id);
      deleteModal.toggle(false);
    } catch {
      toast.error(workspace("couldNotSaveTryAgainInAMoment"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <SettingsLayouts.Root loading={isLoading} data-testid="ProjectsPage/container">
      <SettingsLayouts.Header
        icon={SvgFolder}
        title={sidebar("projects.title")}
        actions={[
          <Button key="create" icon={SvgFolderPlus} onClick={() => createModal.toggle(true)}>
            {sidebar("newProject.label")}
          </Button>,
        ]}
      >
        {(projects.length > 0 || search) && (
          <NativeInput
            type="search"
            aria-label={copy("searchProjects")}
            placeholder={copy("searchProjects")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-h-11 w-full rounded-xl border border-border-02 bg-background-neutral-00 px-3 text-sm text-text-05"
          />
        )}
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
        {error && (
          <ResponsiveLayout display="flex" className="items-center gap-2">
            <p role="alert" className="text-sm text-text-03">{copy("projectsUnavailable")}</p>
            <Button prominence="secondary" onClick={() => void refreshProjects()}>
              {workspace("tryAgain")}
            </Button>
          </ResponsiveLayout>
        )}
        {visible.length > 0 ? (
          <ul className="grid gap-3 sm:grid-cols-2">
            {visible.map((project) => (
              <li key={project.id} className="flex min-w-0 items-center gap-2 rounded-xl border border-border-01 bg-background-neutral-00 pr-2">
                <NavLink
                  {...appPosition.linkToProject(project.id)}
                  className="flex h-full min-w-0 flex-1 items-start gap-3 rounded-l-xl p-4 hover:bg-background-neutral-01 focus-visible:outline-2"
                >
                  <SvgFolder size={20} className="shrink-0 text-text-03" />
                  <span className="min-w-0">
                    <span className="block break-words font-semibold text-text-05">{project.name}</span>
                    {project.description && (
                      <span className="mt-1 block break-words text-sm text-text-03">{project.description}</span>
                    )}
                  </span>
                </NavLink>
                {(!project.role || project.role === "owner") && (
                  <Button
                    icon={SvgTrash}
                    prominence="tertiary"
                    tooltip={projectCopy("delete.label")}
                    aria-label={projectCopy("delete.label")}
                    onClick={() => {
                      setDeleteTarget(project);
                      deleteModal.toggle(true);
                    }}
                  />
                )}
              </li>
            ))}
          </ul>
        ) : !error && (
          <p role="status" className="text-sm text-text-03">
            {search ? workspace("nothingMatchesTheseFilters") : copy("noProjects")}
          </p>
        )}
      </SettingsLayouts.Body>
      <createModal.Provider>
        <CreateProjectModal />
      </createModal.Provider>
      <deleteModal.Provider>
        {deleteTarget && (
          <ConfirmationModalLayout
            title={projectCopy("deleteModal.title")}
            icon={SvgTrash}
            onClose={() => { if (!deleting) deleteModal.toggle(false); }}
            submit={
              <Button variant="danger" disabled={deleting} onClick={() => void confirmDelete()}>
                {projectCopy("deleteModal.confirmButton.label")}
              </Button>
            }
          >
            {projectCopy("deleteModal.message")}
          </ConfirmationModalLayout>
        )}
      </deleteModal.Provider>
    </SettingsLayouts.Root>
  );
}
