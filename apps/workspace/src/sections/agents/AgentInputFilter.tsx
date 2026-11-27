"use client";

import { useTranslations } from "next-intl";
import { Dropdown, SelectButton } from "@opal/components";
import { SvgBookOpen, SvgFileText, SvgFilter, SvgSpreadsheetFile } from "@opal/icons";
import type { AgentInputType } from "@/lib/agents/pilots";

const options = [
  { value: "all", icon: SvgFilter },
  { value: "knowledge", icon: SvgBookOpen },
  { value: "spreadsheet", icon: SvgSpreadsheetFile },
  { value: "meetingNotes", icon: SvgFileText },
] as const;

export function AgentInputFilter({
  value,
  onChange,
}: {
  value: AgentInputType | "all";
  onChange: (value: AgentInputType | "all") => void;
}) {
  const t = useTranslations("agents.filters.inputType");

  return (
    <Dropdown>
      <Dropdown.Trigger asChild>
        <SelectButton
          variant="select-filter"
          chevron
          labelFont="main-ui-action"
          icon={SvgFilter}
          state={value === "all" ? "empty" : "selected"}
          onClear={() => onChange("all")}
        >
          {value === "all" ? t("label") : t(value)}
        </SelectButton>
      </Dropdown.Trigger>
      <Dropdown.Data
        label={t("label")}
        value={value}
        items={options.map((option) => ({
          ...option,
          kind: "option",
          title: t(option.value),
        }))}
        onSelect={(option) => {
          const choice = options.find(({ value }) => value === option.value);
          if (choice) onChange(choice.value);
        }}
      />
    </Dropdown>
  );
}
