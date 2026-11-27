import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations as useWorkspaceTranslations } from "next-intl";
import SectionTabs from "@/sections/sidebar/SectionTabs";

const TABS = [
  { href: "/app/sources/integrations", label: "Integrations" },
  { href: "/app/sources/tools", label: "Tools" },
  { href: "/app/sources/skills", label: "Skills", matchDescendants: true },
  { href: "/app/sources/discover", label: "Discover" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  return (
    <ResponsiveLayout display="flex" className="w-full flex-col">
      <SectionTabs label={workspaceText("sources")} tabs={TABS} />
      {children}
    </ResponsiveLayout>
  );
}
