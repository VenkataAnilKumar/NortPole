"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeSelect } from "@opal/components";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import { useState } from "react";
import { NavLink } from "@opal/navigation";
import useSWR from "swr";
import { useDocumentSets } from "@/app/admin/documents/sets/hooks";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { uploadFiles } from "@/lib/projects/svc";
import { UserFileStatus, type ProjectFile } from "@/lib/projects/types";
import { useSettings } from "@/lib/settings/hooks";
import { SWR_KEYS } from "@/lib/swr-keys";

interface DriveCsvSource {
  app_id: number;
  folder_id: string;
  filename_pattern: string;
}

interface DriveConnection {
  id: number;
  name: string;
  app_type: string;
  authenticated: boolean;
}

export interface ExpenseInputs {
  library_id: number;
  csv_file_id: string | null;
  drive_source: DriveCsvSource | null;
  policy_title: string;
}

export default function ScheduledExpenseInputs({
  value,
  onChange,
  inputClass,
}: {
  value: ExpenseInputs;
  onChange: (value: Partial<ExpenseInputs>) => void;
  inputClass: string;
}) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  const libraries = useDocumentSets();
  const drive = value.drive_source;
  const personalIntegrations = useSettings().nortpole_craft_enabled === true;
  const connections = useSWR<DriveConnection[]>(
    drive && personalIntegrations ? SWR_KEYS.buildExternalApps : null, errorHandlingFetcher,
  );
  const connected = connections.data?.filter(
    (app) => app.app_type === "GOOGLE_DRIVE" && app.authenticated,
  );
  const { data, mutate } = useSWR<ProjectFile[]>(drive ? null : "/api/user/files/recent", errorHandlingFetcher, {
    refreshInterval: (files) => files?.some(
      (file) => file.id === value.csv_file_id &&
        (file.status === UserFileStatus.PROCESSING || file.status === UserFileStatus.INDEXING)
    ) ? 3000 : 0,
  });
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const csvs = (data ?? []).filter((file) => file.name.toLowerCase().endsWith(".csv"));
  const selected = csvs.find((file) => file.id === value.csv_file_id);
  const uploadCsv = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv") || file.size > 12_000) {
      setUploadError("Choose one CSV of up to 12 KB.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = (await uploadFiles([file])).user_files[0];
      if (!uploaded) throw new Error("Upload rejected");
      onChange({ csv_file_id: uploaded.id, drive_source: null });
      await mutate();
    } catch {
      setUploadError("Could not upload the CSV. Try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <ResponsiveLayout display="grid" className="gap-2 sm:grid-cols-2">
      <label className="grid gap-1 text-sm text-text-05">{workspaceText("knowledgeLibrary")}<NativeSelect className={inputClass} value={value.library_id || ""} onChange={(event) =>
          onChange({ library_id: Number(event.target.value), policy_title: "" })
        }>
          <option value="">{workspaceText("chooseALibrary")}</option>
          {libraries.data?.map((library) => <option key={library.id} value={library.id}>{library.name}</option>)}
        </NativeSelect>
      </label>
      <label className="grid gap-1 text-sm text-text-05">{workspaceText("policyTitleOptional")}<NativeInput className={inputClass} maxLength={300} value={value.policy_title}
          onChange={(event) => onChange({ policy_title: event.target.value })} />
      </label>
      <label className="grid gap-1 text-sm text-text-05 sm:col-span-2">{workspaceText("csvSource")}<NativeSelect className={inputClass} value={drive ? "drive" : "upload"} disabled={uploading} onChange={(event) =>
          onChange({
            csv_file_id: null,
            drive_source: event.target.value === "drive" ? { app_id: 0, folder_id: "", filename_pattern: "*.csv" } : null,
          })
        }>
          <option value="upload">{workspaceText("uploadedCsv")}</option>
          <option value="drive">{workspaceText("googleDriveFolder")}</option>
        </NativeSelect>
      </label>
      {drive ? <>
        <label className="grid gap-1 text-sm text-text-05">{workspaceText("googleDriveConnection")}<NativeSelect className={inputClass} value={drive.app_id || ""} onChange={(event) =>
            onChange({ drive_source: { ...drive, app_id: Number(event.target.value) } })
          }>
            <option value="">{workspaceText("chooseAConnection")}</option>
            {drive.app_id > 0 && !connected?.some((app) => app.id === drive.app_id) && (
              <option value={drive.app_id}>{workspaceText("savedConnection")}</option>
            )}
            {connected?.map((app) => <option key={app.id} value={app.id}>{app.name}</option>)}
          </NativeSelect>
        </label>
        <label className="grid gap-1 text-sm text-text-05">{workspaceText("googleDriveFolderLinkOrId")}<NativeInput className={inputClass} value={drive.folder_id} onChange={(event) => {
            const text = event.target.value.trim();
            const folderId = text.match(/^https:\/\/drive\.google\.com\/drive\/(?:u\/\d+\/)?folders\/([\w-]+)(?:[/?#].*)?$/)?.[1];
            onChange({ drive_source: { ...drive, folder_id: folderId ?? text } });
          }} />
        </label>
        <label className="grid gap-1 text-sm text-text-05">{workspaceText("filenamePattern")}<NativeInput className={inputClass} value={drive.filename_pattern} maxLength={200}
            onChange={(event) => onChange({ drive_source: { ...drive, filename_pattern: event.target.value } })} />
        </label>
        {!personalIntegrations && <p className="text-sm text-text-03">{workspaceText("askYourWorkspaceAdministratorToEnablePersonalIntegrationsTo")}</p>}
        {connections.error && <p role="alert" className="text-sm text-status-text-error-05">{workspaceText("couldNotLoadGoogleDriveConnections")}</p>}
        {connected?.length === 0 && (
          <p className="text-sm text-text-03">{workspaceText("connectGoogleDriveIn")}{" "}<NavLink className="underline" href="/app/sources/integrations">{workspaceText("sources")}</NavLink>{" "}{workspaceText("toUseThisOption")}</p>
        )}
        <p className="text-xs text-text-03 sm:col-span-2">{workspaceText("eachRunChecksTheNewestMatchingCsvUpTo")}</p>
      </> : <>
      <label className="grid gap-1 text-sm text-text-05">{workspaceText("expenseCsv")}<NativeSelect className={inputClass} value={value.csv_file_id ?? ""} onChange={(event) =>
          onChange({ csv_file_id: event.target.value || null })
        }>
          <option value="">{workspaceText("chooseAnUploadedCsv")}</option>
          {value.csv_file_id && !selected && <option value={value.csv_file_id}>{workspaceText("savedCsv")}</option>}
          {csvs.map((file) => <option key={file.id} value={file.id}>{file.name}</option>)}
        </NativeSelect>
      </label>
      <label className="grid gap-1 text-sm text-text-05">{workspaceText("uploadCsv")}<NativeInput type="file" className="max-w-full text-sm" accept=".csv,text/csv" disabled={uploading}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void uploadCsv(file);
          }} />
      </label>
      {uploading && <output className="text-sm text-text-03">{workspaceText("uploadingCsv")}</output>}
      {uploadError && <p role="alert" className="text-sm text-status-text-error-05">{uploadError}</p>}
      <p className="text-xs text-text-03 sm:col-span-2">{workspaceText("eachRunUsesThisCsvAndTheCurrentPolicy")}</p>
      </>}
    </ResponsiveLayout>
  );
}
