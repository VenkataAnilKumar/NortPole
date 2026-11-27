import { ResponsiveLayout } from "@opal/layouts";
import { getTranslations } from "next-intl/server";
import SectionTabs from "@/sections/sidebar/SectionTabs";

export default async function Layout({ children }: { children: React.ReactNode }) {
  const t = await getTranslations("sidebar.appSidebar");
  return (
    <ResponsiveLayout display="flex" className="h-full min-h-0 w-full flex-col">
      <SectionTabs
        label={t("agents.title")}
        tabs={[
          {
            href: "/app/agents",
            label: t("exploreAgents.label"),
            matchDescendants: true,
          },
        ]}
      />
      <ResponsiveLayout className="min-h-0 flex-1">{children}</ResponsiveLayout>
    </ResponsiveLayout>
  );
}
