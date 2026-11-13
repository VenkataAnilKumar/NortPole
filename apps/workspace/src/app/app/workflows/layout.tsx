import SectionTabs from "@/sections/sidebar/SectionTabs";

const TABS = [
  { href: "/app/workflows", label: "Start" },
  { href: "/app/workflows/scheduled", label: "Scheduled" },
  { href: "/app/workflows/drafts", label: "My drafts" },
];

/** Workflows: start one from a pack, see the scheduled ones, and follow your drafts. */
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex w-full flex-col">
      <SectionTabs label="Workflows" tabs={TABS} />
      {children}
    </div>
  );
}
