"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useRef, useState, type ChangeEvent } from "react";
import useSWR from "swr";
import { Button } from "@opal/components";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { getUserFileStatuses, uploadFiles } from "@/lib/projects/svc";
import { type ProjectFile, UserFileStatus } from "@/lib/projects/types";
import { isFilePending } from "@/lib/projects/utils";

function fileStatus(status: UserFileStatus) {
  if (isFilePending(status)) return "Processing";
  if (status === UserFileStatus.COMPLETED) return "Ready";
  if (status === UserFileStatus.FAILED) return "Processing failed";
  return status.charAt(0) + status.slice(1).toLowerCase();
}

export default function PersonalKnowledge() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const input = useRef<HTMLInputElement>(null);
  const uploading = useRef(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [uploadIds, setUploadIds] = useState<string[]>([]);
  const {
    data: recentFiles,
    error,
    isLoading,
    mutate,
  } = useSWR<ProjectFile[]>("/api/user/files/recent", errorHandlingFetcher, {
    refreshInterval: (files) => (files?.some((file) => isFilePending(file.status)) ? 2500 : 0),
  });
  const { data: uploadStatuses, error: statusError } = useSWR(
    uploadIds.length ? (["personal-knowledge-upload-status", uploadIds] as const) : null,
    ([, ids]) => getUserFileStatuses(ids),
    { refreshInterval: (files) => (files?.some((file) => isFilePending(file.status)) ? 2500 : 0) },
  );
  const files = new Map(recentFiles?.map((file) => [file.id, file]));
  for (const file of uploadStatuses ?? []) files.set(file.id, file);

  async function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.currentTarget.files ?? []);
    event.currentTarget.value = "";
    if (!selectedFiles.length || uploading.current) return;
    uploading.current = true;
    setIsUploading(true);
    setUploadErrors([]);
    try {
      const result = await uploadFiles(selectedFiles);
      setUploadIds((ids) => [...ids, ...result.user_files.map((file) => file.id)]);
      setUploadErrors(result.rejected_files.map((file) => `${file.file_name}: ${file.reason}`));
      void mutate();
    } catch {
      setUploadErrors(["Could not upload your files. Please try again."]);
    } finally {
      uploading.current = false;
      setIsUploading(false);
    }
  }

  return (
    <section aria-labelledby="personal-knowledge" className="flex flex-col gap-3">
      <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-2">
        <h2 id="personal-knowledge" className="text-base font-semibold text-text-05">{workspaceText("myFiles")}</h2>
        <Button
          prominence="secondary"
          onClick={() => input.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? "Uploading…" : "Add files"}
        </Button>
        <NativeInput
          ref={input}
          type="file"
          multiple
          hidden
          onChange={addFiles}
          aria-label={workspaceText("addPersonalKnowledgeFiles")}
        />
      </ResponsiveLayout>
      <p className="text-sm text-text-03">{workspaceText("filesAddedHereArePrivateYouCanPickThem")}</p>
      {uploadErrors.length > 0 && (
        <ul role="alert" className="list-disc space-y-1 ps-5 text-sm text-text-05">
          {uploadErrors.map((message, index) => (
            <li key={`${index}-${message}`}>{message}</li>
          ))}
        </ul>
      )}
      {statusError && (
        <p role="status" className="text-sm text-text-03">{workspaceText("uploadStatusIsTemporarilyUnavailable")}</p>
      )}
      {error && (
        <p role="alert" className="text-sm text-text-05">{workspaceText("couldNotLoadYourFiles")}</p>
      )}
      {files.size > 0 ? (
        <ul className="divide-y divide-border-01 rounded-xl border border-border-01 bg-background-neutral-00 px-4">
          {Array.from(files.values(), (file) => (
            <li
              key={file.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span className="min-w-0 break-words text-text-05">{file.name}</span>
              <span className="text-text-03">{fileStatus(file.status)}</span>
            </li>
          ))}
        </ul>
      ) : (
        !error && (
          <p role="status" className="text-sm text-text-03">
            {isLoading ? "Loading your files…" : "No personal files yet."}
          </p>
        )
      )}
    </section>
  );
}
