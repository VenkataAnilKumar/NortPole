import SkillEditorPage from "@/views/SkillEditorPage";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ draft?: string | string[] }>;
}) {
  const { draft } = await searchParams;
  return (
    <SkillEditorPage
      surface="sources"
      draftId={typeof draft === "string" ? draft : undefined}
    />
  );
}
