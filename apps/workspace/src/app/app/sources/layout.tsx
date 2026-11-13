import SectionTabs from "@/sections/sidebar/SectionTabs";

const TABS = [
  { href: "/app/sources/connectors", label: "Connectors" },
  { href: "/app/sources/skills", label: "Skills" },
  { href: "/app/sources/plugins", label: "Plugins" },
];

/** Sources: the connected systems, the know-how and the tools this workspace offers. Discover comes first from R4. */
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex w-full flex-col">
      <SectionTabs label="Sources" tabs={TABS} />
      {children}
    </div>
  );
}
