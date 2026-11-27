"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeSelect } from "@opal/components";
import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@opal/components";
import { SvgUploadSquare } from "@opal/icons";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type { ProjectFile } from "@/lib/projects/types";
import { UserFileStatus } from "@/lib/projects/types";

const MAX_CSV_BYTES = 12_000;
const fieldClass =
  "w-full rounded-lg border border-border-01 bg-background-neutral-00 px-2 py-1.5 text-sm text-text-05";

export default function ExpenseReviewForm({
  libraries,
  files,
  initialLibrary = "",
  initialTitle = "",
  disabled,
  onUpload,
  onCancel,
  onRun,
}: {
  libraries: { id: number; name: string }[];
  files: ProjectFile[];
  initialLibrary?: string;
  initialTitle?: string;
  disabled: boolean;
  onUpload: (files: File[]) => void;
  onCancel: () => void;
  onRun: (library: string, policyTitle: string) => void;
}) {
  const t = useTranslations("chat.expenseReview");
  const id = useId();
  const [libraryName, setLibraryName] = useState(initialLibrary);
  const [policyTitle, setPolicyTitle] = useState(initialTitle);
  const [invalidFile, setInvalidFile] = useState(false);
  const library = libraries.find(({ name }) => name === libraryName);
  const { data: policies } = useSWR<{ documents: { id: string; title: string }[] }>(
    library ? `/api/manage/document-set/${library.id}/documents` : null,
    errorHandlingFetcher,
  );
  const file = files.length === 1 ? files[0] : undefined;
  const readyFile =
    file?.name.toLowerCase().endsWith(".csv") &&
    (file.status === UserFileStatus.COMPLETED || file.status === UserFileStatus.SKIPPED);

  return (
    <form
      className="m-2 grid gap-3 rounded-xl border border-border-01 p-3"
      aria-labelledby={`${id}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        if (library && readyFile && !disabled) onRun(library.name, policyTitle.trim());
      }}
    >
      <h2 id={`${id}-title`} className="font-semibold text-text-05">
        {t("title")}
      </h2>
      <ResponsiveLayout display="grid" className="gap-2 sm:grid-cols-2">
        <label className="grid min-w-0 gap-1 text-sm text-text-04">
          {t("library")}
          <NativeSelect
            className={fieldClass}
            value={libraryName}
            onChange={(event) => {
              setLibraryName(event.target.value);
              setPolicyTitle("");
            }}
          >
            <option value="">{t("chooseLibrary")}</option>
            {libraries.map(({ id, name }) => (
              <option key={id} value={name}>
                {name}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid min-w-0 gap-1 text-sm text-text-04">
          {t("policyTitle")}
          <NativeInput
            className={fieldClass}
            maxLength={300}
            list={`${id}-policies`}
            value={policyTitle}
            disabled={!library}
            onChange={(event) => setPolicyTitle(event.target.value)}
          />
          <datalist id={`${id}-policies`}>
            {policies?.documents.map(({ id, title }) => (
              <option key={id} value={title}>{title}</option>
            ))}
          </datalist>
        </label>
      </ResponsiveLayout>
      <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2 text-sm text-text-04">
        <label className="inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 hover:bg-background-neutral-01 focus-within:outline">
          <SvgUploadSquare aria-hidden="true" className="size-4" />
          {t("uploadCsv")}
          <NativeInput
            type="file"
            className="sr-only"
            accept=".csv,text/csv"
            onChange={(event) => {
              const csv = event.target.files?.[0];
              event.target.value = "";
              if (!csv) return;
              const valid = csv.name.toLowerCase().endsWith(".csv") && csv.size <= MAX_CSV_BYTES;
              setInvalidFile(!valid);
              if (valid) onUpload([csv]);
            }}
          />
        </label>
        <span>{file?.name ?? t("csvDescription")}</span>
      </ResponsiveLayout>
      {(invalidFile || (files.length > 0 && !readyFile)) && (
        <p role="status" className="text-xs text-text-04">
          {invalidFile || files.length !== 1 || !file?.name.toLowerCase().endsWith(".csv")
            ? t("oneCsv")
            : t("waitForCsv")}
        </p>
      )}
      <ResponsiveLayout display="flex" className="justify-end gap-2">
        <Button type="button" prominence="secondary" onClick={onCancel}>
          {t("cancel")}
        </Button>
        <Button type="submit" disabled={!library || !readyFile || disabled}>
          {t("run")}
        </Button>
      </ResponsiveLayout>
    </form>
  );
}
