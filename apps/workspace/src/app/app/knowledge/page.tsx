import LibrariesPage from "@/sections/libraries/LibrariesPage";
import { ValidSources } from "@/lib/connectors/types/source";
import { workspaceSourceKey } from "@/sections/sources/integrations";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ source?: string | string[] }>;
}) {
  const { source } = await searchParams;
  const key = typeof source === "string" ? workspaceSourceKey(source) : undefined;
  const sourceFilter = Object.values(ValidSources).find((value) => value === key);
  return <LibrariesPage sourceFilter={sourceFilter} />;
}
