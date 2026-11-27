import { ResponsiveLayout } from "@opal/layouts";
import { getTranslations as getWorkspaceTranslations } from "next-intl/server";
import SectionTabs from "@/sections/sidebar/SectionTabs";
import { getTranslations } from "next-intl/server";

const TABS = [
  { href: "/app/workflows", label: "Start" },
  { href: "/app/workflows/scheduled", label: "Scheduled" },
  { href: "/app/workflows/drafts", label: "My drafts" },
];

export default async function Layout({ children }: { children: React.ReactNode }) {
  const workspaceText = await getWorkspaceTranslations("workspaceUi");
  const t = await getTranslations("chat.workflowRuns");
  return (
    <ResponsiveLayout display="flex" className="w-full flex-col">
      <SectionTabs
        label={workspaceText("workflows")}
        tabs={[...TABS, { href: "/app/workflows/runs", label: t("tab") }]}
      />
      {children}
    </ResponsiveLayout>
  );
}
