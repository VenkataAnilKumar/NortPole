"use client";

import { useTranslations } from "next-intl";
import { SettingsLayouts } from "@opal/layouts";
import { SvgEvolvXSIOctagon } from "@opal/icons";
import { usePathname } from "@opal/navigation";

/** The agent editor while it loads, titled for a new agent or an edit. */
export default function AgentEditorLoading() {
  const t = useTranslations("agents");
  const pathname = usePathname();
  return (
    <SettingsLayouts.Loading
      icon={SvgEvolvXSIOctagon}
      title={
        pathname === "/app/agents/create"
          ? t("editor.header.createTitle")
          : t("editor.header.editTitle")
      }
    />
  );
}
