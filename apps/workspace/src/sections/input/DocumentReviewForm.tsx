"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useId, useState } from "react";
import { Button } from "@opal/components";
import { SvgUploadSquare } from "@opal/icons";
import { UserFileStatus, type ProjectFile } from "@/lib/projects/types";

const supported = /\.(pdf|docx|md|txt)$/i;
const field = "w-full rounded-lg border border-border-01 bg-background-neutral-00 px-2 py-1.5 text-sm text-text-05";

export default function DocumentReviewForm({
  libraries, packs, files, initialLibrary = "", initialPack = "", disabled, onUpload, onCancel, onRun,
}: {
  libraries: { id: number; name: string }[];
  packs: { pack_id: string; name: string }[];
  files: ProjectFile[];
  initialLibrary?: string;
  initialPack?: string;
  disabled: boolean;
  onUpload: (files: File[]) => void;
  onCancel: () => void;
  onRun: (library: string, pack: string) => void;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const titleId = useId();
  const [library, setLibrary] = useState(initialLibrary);
  const [pack, setPack] = useState(initialPack);
  const [invalid, setInvalid] = useState(false);
  const file = files.length === 1 ? files[0] : undefined;
  const ready = Boolean(
    file && supported.test(file.name) &&
    (file.status === UserFileStatus.COMPLETED || file.status === UserFileStatus.SKIPPED)
  );
  const canRun = !disabled && !invalid && ready && libraries.some((item) => item.name === library);
  return (
    <form className="m-2 grid gap-3 rounded-xl border border-border-01 p-3" aria-labelledby={titleId} onSubmit={(event) => {
      event.preventDefault();
      if (canRun) onRun(library, pack);
    }}>
      <h2 id={titleId} className="font-semibold text-text-05">{workspaceText("documentReview")}</h2>
      <ResponsiveLayout display="grid" className="gap-2 sm:grid-cols-2">
        <label className="grid gap-1 text-sm text-text-04">{workspaceText("knowledgeLibrary")}<NativeSelect className={field} value={library} onChange={(event) => setLibrary(event.target.value)}>
            <option value="">{workspaceText("chooseALibrary")}</option>
            {libraries.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
          </NativeSelect>
        </label>
        <label className="grid gap-1 text-sm text-text-04">{workspaceText("packRules")}<NativeSelect className={field} value={pack} onChange={(event) => setPack(event.target.value)}>
            <option value="">{workspaceText("standardReview")}</option>
            {packs.map((item) => <option key={item.pack_id} value={item.pack_id}>{item.name}</option>)}
          </NativeSelect>
        </label>
      </ResponsiveLayout>
      <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2 text-sm text-text-04">
        <label className="inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 hover:bg-background-neutral-01 focus-within:outline">
          <SvgUploadSquare aria-hidden="true" className="size-4" />{workspaceText("attachDocument")}<NativeInput type="file" className="sr-only" accept=".pdf,.docx,.md,.txt" disabled={disabled} onChange={(event) => {
            const attached = event.target.files?.[0];
            event.target.value = "";
            if (!attached) return;
            const valid = supported.test(attached.name) && attached.size <= 5_000_000;
            setInvalid(!valid);
            if (valid) onUpload([attached]);
          }} />
        </label>
        <span>{file?.name ?? "One PDF, DOCX, Markdown or text file, up to 5 MB."}</span>
      </ResponsiveLayout>
      {(invalid || (files.length > 0 && !ready)) && (
        <p role="status" className="text-xs text-text-04">
          {invalid || !file || !supported.test(file.name)
            ? "Attach one supported document of up to 5 MB. Remove any other attachments."
            : "Wait for the document to finish processing."}
        </p>
      )}
      <ResponsiveLayout display="flex" className="justify-end gap-2">
        <Button type="button" prominence="secondary" onClick={onCancel}>{workspaceText("cancel")}</Button>
        <Button type="submit" disabled={!canRun}>{workspaceText("run")}</Button>
      </ResponsiveLayout>
    </form>
  );
}
