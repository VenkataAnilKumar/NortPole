"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeTextArea } from "@opal/components";
import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Modal } from "@opal/components";
import { SvgDownload } from "@opal/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MAX_DOCUMENT_LENGTH } from "@/lib/chat/documentDraft";
import { downloadFile } from "@/lib/download";
import { outputFileName, type SavedOutput } from "@/lib/chat/outputs";
import OutputActions from "./OutputActions";

const field =
  "w-full rounded-lg border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";

export default function DocumentModal({
  onClose,
  initialBody,
  saved,
}: {
  onClose: () => void;
  initialBody?: string;
  saved?: SavedOutput;
}) {
  const t = useTranslations("chat.documentBuilder");
  const id = useId();
  const [name, setName] = useState(saved?.name ?? t("untitled"));
  const [body, setBody] = useState(
    saved?.artifact.kind === "document" ? saved.artifact.payload.body : (initialBody ?? ""),
  );
  const [preview, setPreview] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(false);
  const tooLong = body.length > MAX_DOCUMENT_LENGTH;
  const disabled = !body.trim() || tooLong || exporting;
  const filename = outputFileName(name, t("untitled"));

  const download = async (format: "md" | "docx") => {
    setError(false);
    setExporting(true);
    try {
      if (format === "md")
        downloadFile(`${filename}.md`, { content: body, mimeType: "text/markdown;charset=utf-8" });
      else {
        const { documentDocx } = await import("@/lib/chat/documentExport");
        downloadFile(`${filename}.docx`, { content: await documentDocx(filename, body) });
      }
    } catch {
      setError(true);
    } finally {
      setExporting(false);
    }
  };

  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="xl" maxHeight="92dvh">
        <Modal.Header title={t("title")} onClose={onClose} />
        <Modal.Body alignItems="stretch">
          <ResponsiveLayout display="flex" className="min-w-0 flex-col gap-3">
            <label htmlFor={`${id}-name`} className="text-sm font-medium text-text-05">
              {t("name")}
            </label>
            <NativeInput
              id={`${id}-name`}
              className={field}
              value={name}
              maxLength={150}
              onChange={(event) => setName(event.target.value)}
            />
            <ResponsiveLayout display="flex" className="items-center justify-between gap-2">
              <label htmlFor={`${id}-body`} className="text-sm font-medium text-text-05">
                {t("body")}
              </label>
              <Button
                size="sm"
                prominence="secondary"
                aria-pressed={preview}
                onClick={() => setPreview(!preview)}
              >
                {t(preview ? "edit" : "preview")}
              </Button>
            </ResponsiveLayout>
            {preview ? (
              <article
                aria-label={t("preview")}
                className="min-h-64 break-words rounded-lg border border-border-02 p-4 text-text-05 [&_a]:underline [&_h1]:mb-3 [&_h1]:text-2xl [&_h2]:mb-2 [&_h2]:text-xl [&_h3]:mb-2 [&_h3]:text-lg [&_li_p]:mb-0 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:ps-6 [&_p]:mb-3 [&_pre]:overflow-auto [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:ps-6"
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  skipHtml
                  components={{
                    img: ({ alt }) => alt || null,
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {body}
                </ReactMarkdown>
              </article>
            ) : (
              <NativeTextArea
                id={`${id}-body`}
                className={`${field} min-h-64 resize-y`}
                value={body}
                onChange={(event) => setBody(event.target.value)}
                placeholder={t("hint")}
              />
            )}
            {(tooLong || error) && (
              <p role="alert" className="text-sm text-status-text-error-05">
                {t(tooLong ? "tooLong" : "exportFailed")}
              </p>
            )}
            <OutputActions
              name={filename}
              artifact={{ kind: "document", payload: { body } }}
              saved={saved}
              disabled={disabled}
            />
          </ResponsiveLayout>
        </Modal.Body>
        <Modal.Footer>
          <Button
            icon={SvgDownload}
            prominence="secondary"
            disabled={disabled}
            onClick={() => void download("md")}
          >
            {t("downloadMarkdown")}
          </Button>
          <Button icon={SvgDownload} disabled={disabled} onClick={() => void download("docx")}>
            {t(exporting ? "exporting" : "downloadWord")}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
