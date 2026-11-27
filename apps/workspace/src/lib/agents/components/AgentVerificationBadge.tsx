import { Badge } from "@opal/components";
import { SvgCheckCircle } from "@opal/icons";
import { useTranslations } from "next-intl";

export default function AgentVerificationBadge({ version }: { version: number }) {
  const t = useTranslations("agents.verification");
  return <Badge icon={SvgCheckCircle} title={t("label")} tooltip={t("version", { version })} />;
}
