import SectionTabs from "@/sections/sidebar/SectionTabs";

const TABS = [
  { href: "/app/sources/skills", label: "Skills" },
  { href: "/app/sources/connectors", label: "Connectors" },
  { href: "/app/sources/plugins", label: "Plugins" },
];

/** Sources: the know-how, the connected systems and the tools this workspace offers. */
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex w-full flex-col">
      <SectionTabs label="Sources" tabs={TABS} />
      {children}
    </div>
  );
}
