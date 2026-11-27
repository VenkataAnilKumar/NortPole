"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { useState } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import useSWR from "swr";
import { Button, Modal } from "@opal/components";
import { SvgFileText, SvgSpreadsheetFile } from "@opal/icons";
import { errorHandlingFetcher, errorHandlingFetchWith } from "@/lib/fetcher";
import {
  projectOutputsKey,
  type OutputDetail,
  type OutputSummary,
  type SavedOutput,
} from "@/lib/chat/outputs";

const loading = () => null;
const DocumentEditor = dynamic(() => import("@/sections/chat/DocumentModal"), { loading });
const PresentationEditor = dynamic(() => import("@/sections/chat/PresentationModal"), { loading });
const SpreadsheetEditor = dynamic(() => import("@/sections/chat/SpreadsheetModal"), { loading });

export default function ProjectOutputs({ projectId, canEdit }: { projectId: number; canEdit: boolean }) {
  const t = useTranslations("chat.outputs");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<SavedOutput | null>(null);
  const [opening, setOpening] = useState(false);
  const [failed, setFailed] = useState(false);
  const key = projectOutputsKey(projectId);
  const { data, error, mutate } = useSWR<OutputSummary[]>(key, errorHandlingFetcher);

  const edit = async (id: string) => {
    setFailed(false);
    setOpening(true);
    try {
      const output = await errorHandlingFetchWith<OutputDetail>(`${key}/${id}`, { cache: "no-store" });
      setEditing({ ...output, projectId });
    } catch {
      setFailed(true);
    } finally {
      setOpening(false);
    }
  };
  const close = () => {
    setEditing(null);
    void mutate();
  };

  return (
    <section aria-label={t("title")} className="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 className="text-sm font-medium text-text-05">{t("title")}</h2>
        <p className="text-sm text-text-03">{t("projectDescription")}</p>
      </div>
      <Button prominence="tertiary" icon={SvgFileText} onClick={() => setOpen(true)}>
        {t("view")}
      </Button>
      {open && !editing && (
        <Modal open onOpenChange={(value) => setOpen(value)}>
          <Modal.Content width="md" maxHeight="85dvh">
            <Modal.Header title={t("title")} onClose={() => setOpen(false)} />
            <Modal.Body alignItems="stretch">
              <ResponsiveLayout display="flex" className="min-w-0 flex-col gap-2">
                {(error || failed) && (
                  <p role="alert" className="text-sm text-text-04">
                    {t("openFailed")}
                  </p>
                )}
                {opening && (
                  <p role="status" className="text-sm text-text-04">
                    {t("working")}
                  </p>
                )}
                {!data && !error && (
                  <p role="status" className="text-sm text-text-04">
                    {t("loading")}
                  </p>
                )}
                {data?.length === 0 && <p className="text-sm text-text-04">{t("empty")}</p>}
                {data?.map(({ id, name, kind }) => (
                  <Button
                    key={id}
                    icon={kind === "spreadsheet" ? SvgSpreadsheetFile : SvgFileText}
                    prominence="tertiary"
                    aria-label={t("open", { name, kind: t(kind) })}
                    disabled={opening}
                    onClick={() => void edit(id)}
                  >
                    {name}
                  </Button>
                ))}
              </ResponsiveLayout>
            </Modal.Body>
          </Modal.Content>
        </Modal>
      )}
      {!canEdit && editing && <OutputPreview saved={editing} close={close} />}
      {canEdit && editing?.kind === "document" && <DocumentEditor saved={editing} onClose={close} />}
      {canEdit && editing?.kind === "presentation" && <PresentationEditor saved={editing} onClose={close} />}
      {canEdit && editing?.kind === "spreadsheet" && <SpreadsheetEditor saved={editing} onClose={close} />}
    </section>
  );
}

function OutputPreview({ saved, close }: { saved: SavedOutput; close: () => void }) {
  const artifact = saved.artifact;
  return (
    <Modal open onOpenChange={(open) => { if (!open) close(); }}>
      <Modal.Content width="lg" maxHeight="85dvh">
        <Modal.Header title={saved.name} onClose={close} />
        <Modal.Body alignItems="stretch">
          <div className="min-w-0 space-y-3 text-sm text-text-05">
            {artifact.kind === "document" && <pre className="whitespace-pre-wrap break-words font-sans">{artifact.payload.body}</pre>}
            {artifact.kind === "presentation" && artifact.payload.slides.map((slide, index) => (
              <section className="space-y-2 rounded-lg border border-border-01 p-3" key={index}>
                <h3 className="font-semibold">{slide.title}</h3>
                <p className="whitespace-pre-wrap break-words">{slide.text}</p>
                {slide.image && slide.image.data.startsWith("data:image/png;base64,") && (
                  <img className="h-auto max-w-full" src={slide.image.data} alt={slide.image.name} />
                )}
              </section>
            ))}
            {artifact.kind === "spreadsheet" && (
              <div className="overflow-auto">
                <table className="border-collapse">
                  <tbody>
                    {artifact.payload.rows.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {row.map((cell, columnIndex) => (
                          <td className="border border-border-01 px-2 py-1" key={columnIndex}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Modal.Body>
      </Modal.Content>
    </Modal>
  );
}
