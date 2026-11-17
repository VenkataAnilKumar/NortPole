import SectionTabs from "@/sections/sidebar/SectionTabs";

const TABS = [
  { href: "/app/sources/connectors", label: "Connectors" },
  { href: "/app/sources/plugins", label: "Plugins" },
  { href: "/app/sources/skills", label: "Skills" },
  { href: "/app/sources/discover", label: "Discover" },
];

/** Sources: the connected systems, the tools and the know-how this workspace offers, then Discover for finding and adding more. */
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex w-full flex-col">
      <SectionTabs label="Sources" tabs={TABS} />
      {children}
    </div>
  );
}
