"use client";

import { NativeInput } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useId, useState } from "react";
import { useNavigation } from "@opal/navigation";
import useSWR, { mutate as mutateCache } from "swr";
import { Button } from "@opal/components";
import { invalidateNotificationCaches } from "@/lib/notifications/api";
import { getUserFileStatuses, uploadFiles } from "@/lib/projects/svc";
import { UserFileStatus, type ProjectFile } from "@/lib/projects/types";

const supported = /\.(pdf|docx|md|txt)$/i;
const ready = (status: UserFileStatus) => status === UserFileStatus.COMPLETED || status === UserFileStatus.SKIPPED;
const pending = (status: UserFileStatus) => status === UserFileStatus.PROCESSING || status === UserFileStatus.INDEXING;

export default function DocumentRevisionForm({ reviewId, library, pack }: {
  reviewId: number;
  library: string;
  pack: string | null;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const headingId = useId();
  const navigation = useNavigation();
  const [file, setFile] = useState<ProjectFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const status = useSWR(
    file && pending(file.status) ? ["document-revision-status", file.id] as const : null,
    async ([, id]) => (await getUserFileStatuses([id]))[0]?.status ?? UserFileStatus.FAILED,
    { refreshInterval: (current) => current && pending(current) ? 1500 : 0 },
  );
  const state = status.data ?? file?.status;
  const choose = async (upload: File) => {
    setFile(null);
    setError("");
    if (!supported.test(upload.name) || upload.size > 5_000_000) {
      setError("Choose one PDF, DOCX, Markdown or text file up to 5 MB.");
      return;
    }
    setUploading(true);
    try {
      const uploaded = (await uploadFiles([upload])).user_files[0];
      if (!uploaded) throw new Error("The file could not be uploaded.");
      setFile(uploaded);
    } catch {
      setError("The file could not be uploaded.");
    } finally {
      setUploading(false);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !state || !ready(state) || running) return;
    setRunning(true);
    setError("");
    try {
      const response = await fetch(`/api/chat/document-reviews/${reviewId}/revisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: file.id }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok || !Number.isSafeInteger(result?.message_id)) {
        throw new Error(typeof result?.detail === "string" ? result.detail : "The revised review could not finish.");
      }
      void mutateCache((key) => typeof key === "string" && (
        key.startsWith("/api/chat/workflow-run-feed") || key === `/api/chat/document-reviews/${reviewId}`
      ));
      void invalidateNotificationCaches();
      navigation.go(`/app/workflows/runs?review=${result.message_id}`);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The revised review could not finish.");
      setRunning(false);
    }
  };

  return (
    <form aria-labelledby={headingId} onSubmit={submit} className="grid gap-3 rounded-xl border border-border-01 p-4">
      <div>
        <h2 id={headingId} className="font-semibold text-text-05">{workspaceText("reviewARevisedDocument")}</h2>
        <p className="mt-1 break-words text-sm text-text-03">{library}{pack && ` · ${pack}`}</p>
      </div>
      <label className="grid gap-1 text-sm text-text-05">{workspaceText("attachRevisedDocument")}<NativeInput type="file" accept=".pdf,.docx,.md,.txt" disabled={uploading || running}
          onChange={(event) => {
            const selected = event.target.files?.[0];
            event.target.value = "";
            if (selected) void choose(selected);
          }} />
      </label>
      {file && <p className="break-words text-sm text-text-03">{file.name}</p>}
      {state && pending(state) && !status.error && <output className="text-sm text-text-03">{workspaceText("processingTheDocument")}</output>}
      {(status.error || (state && !ready(state) && !pending(state))) && (
        <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("couldNotProcessTheAttachmentChooseTheFileAgain")}</p>
      )}
      {error && <p role="alert" className="text-sm text-status-text-error-05">{error}</p>}
      <div>
        <Button type="submit" disabled={uploading || running || !state || !ready(state)}>
          {running ? "Reviewing…" : uploading ? "Uploading…" : "Review revision"}
        </Button>
      </div>
    </form>
  );
}
