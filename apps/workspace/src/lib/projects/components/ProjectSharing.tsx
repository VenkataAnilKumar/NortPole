"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState, type FormEvent } from "react";
import useSWR from "swr";
import { Button, Modal } from "@opal/components";
import { SvgShare } from "@opal/icons";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { useProjectsContext } from "@/lib/projects/providers";
import type { Project } from "@/lib/projects/types";

type MemberRole = "viewer" | "editor";
type Member = { user_id: string; email: string; name: string | null; role: MemberRole };

const selectStyle = "rounded-lg border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";

export function ProjectSharing({ project }: { project: Project }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [open, setOpen] = useState(false);
  if (project.role && project.role !== "owner") return null;
  return (
    <>
      <Button icon={SvgShare} prominence="secondary" onClick={() => setOpen(true)}>{workspaceText("shareProject")}</Button>
      {open && <SharingDialog project={project} close={() => setOpen(false)} />}
    </>
  );
}

function SharingDialog({ project, close }: { project: Project; close: () => void }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>("viewer");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [remove, setRemove] = useState<Member | null>(null);
  const [demote, setDemote] = useState<Member | null>(null);
  const { fetchProjects, refreshCurrentProjectDetails } = useProjectsContext();
  const path = `/api/user/projects/${project.id}/members`;
  const members = useSWR<Member[]>(path, errorHandlingFetcher);
  const change = async (method: string, endpoint: string, body?: { email?: string; role: MemberRole }) => {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(endpoint, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(typeof payload?.detail === "string" ? payload.detail : "Project access could not be updated.");
      }
      setRemove(null);
      setDemote(null);
      await Promise.allSettled([members.mutate(), fetchProjects(), refreshCurrentProjectDetails()]);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Project access could not be updated.");
      return false;
    } finally {
      setPending(false);
    }
  };

  const add = async (event: FormEvent) => {
    event.preventDefault();
    if (await change("POST", path, { email: email.trim(), role })) setEmail("");
  };

  return (
    <Modal open onOpenChange={(next) => { if (!next && !pending) close(); }}>
      <Modal.Content width="md" maxHeight="85dvh">
        <Modal.Header title={`Share ${project.name}`} onClose={pending ? undefined : close} />
        <Modal.Body alignItems="stretch">
          <ResponsiveLayout display="flex" className="flex-col gap-4 text-sm text-text-05">
            <p className="text-text-03">{workspaceText("addingSomeoneGivesThemAccessToProjectChatTranscripts")}</p>
            <form className="flex flex-wrap items-end gap-2" onSubmit={add}>
              <label className="flex min-w-40 flex-1 flex-col gap-1">{workspaceText("workspaceEmail")}<NativeInput
                  className={selectStyle}
                  type="email"
                  required
                  value={email}
                  disabled={pending}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1">{workspaceText("role")}<NativeSelect aria-label={workspaceText("role")} className={selectStyle} value={role} disabled={pending} onChange={(event) => setRole(event.target.value as MemberRole)}>
                  <option value="viewer">{workspaceText("viewer")}</option>
                  <option value="editor">{workspaceText("editor")}</option>
                </NativeSelect>
              </label>
              <Button type="submit" disabled={pending || !email.trim()}>{workspaceText("addMember")}</Button>
            </form>
            <p className="text-text-03">{workspaceText("viewersCanReadProjectContentEditorsCanAlsoEdit")}</p>
            {error && <p role="alert" className="text-status-text-error-05">{error}</p>}
            {members.error && <p role="alert">{workspaceText("projectMembersCouldNotBeLoaded")}</p>}
            <h3 className="font-semibold">{workspaceText("peopleWithAccess")}</h3>
            <ul className="divide-y divide-border-01">
              <li className="flex justify-between gap-3 py-2"><span>{workspaceText("you")}</span><span>{workspaceText("owner")}</span></li>
              {members.data?.map((member) => (
                <li key={member.user_id} className="flex flex-wrap items-center gap-2 py-2">
                  <div className="min-w-0 flex-1 break-all">
                    {member.name && <p className="font-semibold">{member.name}</p>}
                    <p>{member.email}</p>
                  </div>
                  <NativeSelect
                    aria-label={`Role for ${member.email}`}
                    className={selectStyle}
                    disabled={pending || !!remove || !!demote}
                    value={member.role}
                    onChange={(event) => {
                      if (event.target.value === "viewer") setDemote(member);
                      else void change("PATCH", `${path}/${member.user_id}`, { role: "editor" });
                    }}
                  >
                    <option value="viewer">{workspaceText("viewer")}</option>
                    <option value="editor">{workspaceText("editor")}</option>
                  </NativeSelect>
                  <Button prominence="tertiary" disabled={pending || !!remove || !!demote} onClick={() => setRemove(member)}>{workspaceText("remove")}</Button>
                </li>
              ))}
            </ul>
            {(remove || demote) && (
              <ResponsiveLayout display="flex" className="flex-col gap-2 rounded-lg border border-border-02 p-3">
                <p className="break-words">
                  {remove ? `Remove access for ${remove.email}?` : `Change ${demote?.email} to Viewer?`}
                  {" "}{workspaceText("anyProjectChatsTheyStartedWillMoveToTheir")}</p>
                <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                  <Button prominence="secondary" disabled={pending} onClick={() => { setRemove(null); setDemote(null); }}>{workspaceText("cancel")}</Button>
                  <Button
                    disabled={pending}
                    onClick={() => {
                      if (remove) void change("DELETE", `${path}/${remove.user_id}`);
                      else if (demote) void change("PATCH", `${path}/${demote.user_id}`, { role: "viewer" });
                    }}
                  >
                    {remove ? "Remove access" : "Change role"}
                  </Button>
                </ResponsiveLayout>
              </ResponsiveLayout>
            )}
          </ResponsiveLayout>
        </Modal.Body>
      </Modal.Content>
    </Modal>
  );
}
