import { NativeInput } from "@opal/components";
import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations } from "next-intl";
import type { AgentPilotInput } from "@/lib/agents/pilots";

export interface ReportingSelection {
  start: string;
  end: string;
  libraryIds: number[];
}

export function ReportingInputs({ libraries, value, onChange, disabled }: {
  libraries: AgentPilotInput["libraries"];
  value: ReportingSelection;
  onChange: (value: ReportingSelection) => void;
  disabled: boolean;
}) {
  const t = useTranslations("agents.reporting");
  const invalidPeriod = value.start && value.end && value.start > value.end;

  return (
    <fieldset disabled={disabled} className="grid gap-2 rounded-lg border border-border-01 px-3 py-2 text-sm">
      <legend className="px-1 font-medium text-text-05">{t("period")}</legend>
      <ResponsiveLayout display="grid" className="gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          {t("startDate")}
          <NativeInput type="date" value={value.start} max={value.end || "9999-12-31"}
            onChange={(event) => onChange({ ...value, start: event.target.value })} />
        </label>
        <label className="flex flex-col gap-1">
          {t("endDate")}
          <NativeInput type="date" value={value.end} min={value.start || undefined} max="9999-12-31"
            onChange={(event) => onChange({ ...value, end: event.target.value })} />
        </label>
      </ResponsiveLayout>
      {invalidPeriod && <p role="status" className="text-status-text-error-05">{t("invalidPeriod")}</p>}
      <fieldset>
        <legend className="mb-1 text-text-04">{t("sources")}</legend>
        {libraries.length === 0 ? <p className="text-text-03">{t("noSources")}</p> : (
          <ResponsiveLayout display="flex" className="max-h-24 flex-wrap gap-x-4 gap-y-1 overflow-y-auto">
            {libraries.map((library) => (
              <label key={library.id} className="flex items-center gap-2">
                <NativeInput type="checkbox" checked={value.libraryIds.includes(library.id)}
                  onChange={(event) => onChange({
                    ...value,
                    libraryIds: event.target.checked
                      ? [...value.libraryIds, library.id]
                      : value.libraryIds.filter((id) => id !== library.id),
                  })} />
                {library.name}
              </label>
            ))}
          </ResponsiveLayout>
        )}
      </fieldset>
    </fieldset>
  );
}
