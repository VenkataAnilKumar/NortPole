import { useTranslations as useWorkspaceTranslations } from "next-intl";
export default function HooksPage() {
  const workspaceText = useWorkspaceTranslations("workspaceUi");
  return (
    <div style={{ padding: 24 }}>{workspaceText("hooksAreNotAvailableInThisBuild")}</div>
  );
}
