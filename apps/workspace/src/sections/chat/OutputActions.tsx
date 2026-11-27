"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeSelect } from "@opal/components";
import { useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import useSWR, { useSWRConfig } from "swr";
import { Button } from "@opal/components";
import { useActiveProject, useProjects } from "@/lib/projects/hooks";
import { useIncognitoOptional } from "@/providers/IncognitoProvider";
import { errorHandlingFetcher } from "@/lib/fetcher";
import {
  knowledgeSnapshot,
  outputDestinationsKey,
  projectOutputsKey,
  type OutputArtifact,
  type OutputSummary,
  type OutputLocation,
} from "@/lib/chat/outputs";

type Destination = { id: number; name: string; is_public: boolean; audience_key: string };
type Choice = "project" | "knowledge";

export default function OutputActions({
  name,
  artifact,
  saved,
  onSave,
  disabled = false,
  projectOnly = false,
}: {
  name: string;
  artifact: OutputArtifact;
  saved?: OutputLocation;
  onSave?: (output: OutputLocation) => void;
  disabled?: boolean;
  projectOnly?: boolean;
}) {
  const t = useTranslations("chat.outputs");
  const id = useId();
  const privacy = useIncognitoOptional();
  const activeProject = useActiveProject();
  const { projects, isLoading: projectsLoading, error: projectsError } = useProjects();
  const { mutate } = useSWRConfig();
  const outputId = useRef(saved?.id);
  const inFlight = useRef(false);
  const [version, setVersion] = useState(saved?.version ?? 0);
  const [mode, setMode] = useState<Choice | null>(null);
  const [project, setProject] = useState(saved?.projectId);
  const [collection, setCollection] = useState<number>();
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState<
    "saved" | "queued" | "failed" | "conflict" | "tooLarge" | null
  >(null);
  const { data: destinations, error: destinationError } = useSWR<Destination[]>(
    mode === "knowledge" && !privacy?.incognitoEnabled ? outputDestinationsKey : null,
    errorHandlingFetcher,
  );
  if (privacy?.incognitoEnabled) return null;

  const projectId = project ?? activeProject?.id;
  const destination = destinations?.find((item) => item.id === collection);
  const selectMode = (value: Choice) => {
    setMode(mode === value ? null : value);
    setNotice(null);
  };
  const submit = async () => {
    if (disabled || inFlight.current || privacy?.incognitoEnabledRef?.current) return;
    if (mode === "project" ? !projectId : !destination) return;
    inFlight.current = true;
    setNotice(null);
    setWorking(true);
    try {
      const saving = mode === "project";
      if (saving) outputId.current ??= crypto.randomUUID();
      const url = saving
        ? `${projectOutputsKey(projectId!)}/${outputId.current}`
        : `/api/manage/document-set/${destination!.id}/outputs`;
      const body = saving
        ? { name, version, artifact }
        : { name, ...knowledgeSnapshot(artifact), audience_key: destination!.audience_key };
      const response = await fetch(url, {
        method: saving ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        if (!saving && response.status === 409) {
          setCollection(undefined);
          void mutate(outputDestinationsKey);
        }
        setNotice(
          response.status === 409 && saving
            ? "conflict"
            : response.status === 413
              ? "tooLarge"
              : "failed",
        );
        return;
      }
      if (saving) {
        const data: OutputSummary = await response.json();
        setVersion(data.version);
        setProject(projectId);
        onSave?.({ ...data, projectId: projectId! });
        void mutate(projectOutputsKey(projectId!));
      }
      setNotice(saving ? "saved" : "queued");
      setMode(null);
    } catch {
      setNotice("failed");
    } finally {
      inFlight.current = false;
      setWorking(false);
    }
  };

  return (
    <section aria-label={t("title")} className="flex flex-col gap-2 border-t border-border-01 pt-2">
      <ResponsiveLayout display="flex" className="flex-wrap gap-1">
        <Button
          size="sm"
          prominence="tertiary"
          aria-expanded={mode === "project"}
          disabled={working || disabled}
          onClick={() => selectMode("project")}
        >
          {t("saveProject")}
        </Button>
        {!projectOnly && <Button
          size="sm"
          prominence="tertiary"
          aria-expanded={mode === "knowledge"}
          disabled={working || disabled}
          onClick={() => selectMode("knowledge")}
        >
          {t("addKnowledge")}
        </Button>}
      </ResponsiveLayout>
      {mode && (
        <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
          <label htmlFor={id} className="text-sm text-text-04">
            {t(mode === "project" ? "project" : "collection")}
          </label>
          <NativeSelect
            id={id}
            value={(mode === "project" ? projectId : collection) ?? ""}
            onChange={(event) => {
              const value = Number(event.target.value) || undefined;
              if (mode === "project") setProject(value);
              else setCollection(value);
            }}
            disabled={working || (mode === "project" && version > 0)}
            className="min-w-0 max-w-full rounded-md border border-border-02 bg-background-neutral-00 p-1.5 text-sm text-text-05"
          >
            <option value="">{t("choose")}</option>
            {mode === "project"
              ? projects.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))
              : destinations?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
          </NativeSelect>
          <Button
            size="sm"
            disabled={disabled || working || (mode === "project" ? !projectId : !destination)}
            onClick={() => void submit()}
          >
            {t(working ? "working" : mode === "project" ? "save" : "add")}
          </Button>
          {mode === "project" && (projectsError || (!projectsLoading && !projects.length)) && (
            <p className="text-xs text-text-04">{t("noProjects")}</p>
          )}
          {mode === "knowledge" && (destinationError || destinations?.length === 0) && (
            <p className="text-xs text-text-04">{t("noCollections")}</p>
          )}
          {mode === "knowledge" && destination && (
            <p className="text-xs text-text-04">
              {t(destination.is_public ? "companyAudience" : "collectionAudience")}
            </p>
          )}
        </ResponsiveLayout>
      )}
      {notice && (
        <p
          role={notice === "saved" || notice === "queued" ? "status" : "alert"}
          className="text-sm text-text-04"
        >
          {t(notice)}
        </p>
      )}
    </section>
  );
}
