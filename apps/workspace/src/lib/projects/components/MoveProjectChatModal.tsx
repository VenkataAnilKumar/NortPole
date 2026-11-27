"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useTranslations } from "next-intl";
import { Button, Text } from "@opal/components";
import { SvgFolderIn } from "@opal/icons";
import { ConfirmationModalLayout } from "@opal/layouts";

export function MoveProjectChatModal({
  projectName,
  createProject = false,
  shared = false,
  onCancel,
  onConfirm,
}: {
  projectName: string;
  createProject?: boolean;
  shared?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const t = useTranslations("sidebar.chatButton.moveConfirmation");
  return (
    <ConfirmationModalLayout
      icon={SvgFolderIn}
      title={t("title", { projectName })}
      onClose={onCancel}
      submit={
        <Button onClick={onConfirm}>
          {t(createProject ? "createAndMove" : "move")}
        </Button>
      }
    >
      <ResponsiveLayout display="flex" className="flex-col gap-3">
        <Text as="p" color="text-03">
          {t("context")}
        </Text>
        <Text as="p" color="text-03">
          {shared ? "Project members can read this chat’s transcript." : t("audience")}
        </Text>
      </ResponsiveLayout>
    </ConfirmationModalLayout>
  );
}
