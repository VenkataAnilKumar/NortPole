import SkillEditorPage from "@/views/SkillEditorPage";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SkillEditorPage surface="sources" skillId={id} />;
}
