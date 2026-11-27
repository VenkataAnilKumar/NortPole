export async function createTemplateDraft(
  packId: string,
  templateId: string
): Promise<`/app/workflows/drafts?task=${string}`> {
  const path = `/api/packs/${encodeURIComponent(packId)}/templates/${encodeURIComponent(templateId)}/task`;
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(
      typeof detail === "string" && detail
        ? detail
        : `Could not create the draft (HTTP ${response.status}).`
    );
  }
  const draft = (await response.json()) as { id: string };
  return `/app/workflows/drafts?task=${encodeURIComponent(draft.id)}`;
}
