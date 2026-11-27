import IntegrationsPage from "@/sections/sources/IntegrationsPage";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ integration?: string | string[] }>;
}) {
  const { integration } = await searchParams;
  const initialIntegration = typeof integration === "string" ? integration : undefined;
  return <IntegrationsPage initialIntegration={initialIntegration} />;
}
