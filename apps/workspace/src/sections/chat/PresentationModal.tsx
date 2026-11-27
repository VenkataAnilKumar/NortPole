"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeTextArea } from "@opal/components";
import { useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Modal } from "@opal/components";
import { SvgDownload } from "@opal/icons";
import { downloadFile } from "@/lib/download";
import {
  deckFromNotes,
  MAX_NOTES_LENGTH,
  MAX_POINTS,
  MAX_SLIDES,
  slidePoints,
  type Slide,
  type SlideKind,
} from "@/lib/chat/presentation";
import { presentationChart, presentationNotes } from "@/lib/chat/presentationFiles";
import { presentationPptx } from "@/lib/chat/presentationExport";
import { outputFileName, type SavedOutput } from "@/lib/chat/outputs";
import type { ChartImage } from "@/lib/chat/presentation";
import OutputActions from "./OutputActions";

type Entry = Slide & { id: number };
type ErrorKey = "importFailed" | "notesTooLong" | "tooManySlides" | "imageFailed" | "exportFailed";
const field =
  "rounded-lg border border-border-02 bg-background-neutral-00 px-3 py-2 text-sm text-text-05";
const slideKinds = ["title", "points", "chart"] as const;

export default function PresentationModal({
  onClose,
  saved,
  initialChart,
}: {
  onClose: () => void;
  saved?: SavedOutput;
  initialChart?: ChartImage;
}) {
  const t = useTranslations("chat.presentationBuilder");
  const sourceId = useId();
  const chartId = useId();
  const notesId = useId();
  const titleId = useId();
  const contentId = useId();
  const [notes, setNotes] = useState("");
  const [source, setSource] = useState("");
  const [slides, setSlides] = useState<Entry[]>(() => {
    const initial: Slide[] =
      saved?.artifact.kind === "presentation"
        ? saved.artifact.payload.slides
        : initialChart
          ? [
              { kind: "title", title: t("untitled"), text: "" },
              { kind: "chart", title: t("chart"), text: "", image: initialChart },
            ]
          : [];
    return initial.map((slide, index) => ({ ...slide, id: index + 1 }));
  });
  const serial = useRef(slides.length);
  const [selectedId, setSelectedId] = useState(initialChart ? 2 : saved ? 1 : 0);
  const [busy, setBusy] = useState<"import" | "image" | "export" | null>(null);
  const [error, setError] = useState<ErrorKey | null>(null);
  const index = slides.findIndex((slide) => slide.id === selectedId);
  const selected = slides[index];
  const outputName = outputFileName(slides[0]?.title ?? "", saved?.name ?? t("untitled"));
  const limitExceeded = notes.length > MAX_NOTES_LENGTH;
  const incomplete = slides.some(
    (slide) =>
      !slide.title.trim() ||
      (slide.kind === "chart"
        ? !slide.image
        : slide.kind === "points" &&
          (!slidePoints(slide.text).length || slidePoints(slide.text).length > MAX_POINTS)),
  );

  const loadNotes = async (file: File) => {
    setBusy("import");
    setError(null);
    try {
      setNotes(await presentationNotes(file));
      setSource(file.name);
    } catch (failure) {
      setError(failure instanceof RangeError ? "notesTooLong" : "importFailed");
    } finally {
      setBusy(null);
    }
  };

  const create = () => {
    if (limitExceeded || !notes.trim()) return;
    const deck = deckFromNotes(notes, { title: t("untitled"), points: t("keyPoints") });
    if (!deck) {
      setError("tooManySlides");
      return;
    }
    const entries = deck.map((slide) => ({ ...slide, id: ++serial.current }));
    setError(null);
    setSlides(entries);
    setSelectedId(entries[0]!.id);
  };

  const edit = (id: number, patch: Partial<Slide>) => {
    setSlides((current) =>
      current.map((slide) => (slide.id === id ? { ...slide, ...patch } : slide)),
    );
  };

  const add = (kind: SlideKind) => {
    if (slides.length >= MAX_SLIDES) return;
    const title =
      kind === "title" ? t("untitled") : kind === "points" ? t("keyPoints") : t("chart");
    const id = ++serial.current;
    const position = index + 1;
    setSlides((current) => [
      ...current.slice(0, position),
      { id, kind, title, text: "" },
      ...current.slice(position),
    ]);
    setError(null);
    setSelectedId(id);
  };

  const move = (offset: number) => {
    const target = index + offset;
    if (!selected || target < 0 || target >= slides.length) return;
    const next = [...slides];
    next.splice(index, 1);
    next.splice(target, 0, selected);
    setSlides(next);
  };

  const remove = () => {
    if (slides.length < 2) return;
    const next = slides.filter((slide) => slide.id !== selectedId);
    setSlides(next);
    setSelectedId(next[Math.min(index, next.length - 1)]!.id);
    setError(null);
  };

  const attachChart = async (file: File) => {
    if (!selected) return;
    setError(null);
    setBusy("image");
    try {
      edit(selected.id, { image: await presentationChart(file) });
    } catch {
      setError("imageFailed");
    } finally {
      setBusy(null);
    }
  };

  const download = async () => {
    if (incomplete || !slides.length) return;
    setError(null);
    setBusy("export");
    try {
      const blob = await presentationPptx(slides);
      downloadFile(`${outputName}.pptx`, { content: blob });
    } catch {
      setError("exportFailed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="lg" maxHeight="92dvh" preventAccidentalClose={false}>
        <Modal.Header title={t("title")} onClose={onClose} />
        <Modal.Body alignItems="stretch">
          <ResponsiveLayout display="grid" className="min-w-0 gap-4">
            {error && (
              <p role="alert" className="text-sm text-status-text-error-05">
                {t(error)}
              </p>
            )}
            {busy === "import" && <output className="text-sm text-text-03">{t("reading")}</output>}
            {!selected ? (
              <>
                <ResponsiveLayout display="grid" className="min-w-0 gap-2 rounded-xl border border-border-01 p-3">
                  <label htmlFor={sourceId} className="text-sm font-medium text-text-05">
                    {t("attachNotes")}
                  </label>
                  <NativeInput
                    id={sourceId}
                    type="file"
                    accept=".pdf,.docx,.md,.txt"
                    disabled={!!busy}
                    className="max-w-full text-sm text-text-04"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      if (file) void loadNotes(file);
                    }}
                  />
                  <p className="break-words text-xs text-text-03">{source || t("documentHint")}</p>
                </ResponsiveLayout>
                <ResponsiveLayout display="grid" className="gap-2 text-sm font-medium text-text-05">
                  <label htmlFor={notesId}>{t("notes")}</label>
                  <NativeTextArea
                    id={notesId}
                    className={field}
                    rows={9}
                    value={notes}
                    maxLength={MAX_NOTES_LENGTH + 1}
                    disabled={!!busy}
                    placeholder={t("notesHint")}
                    onChange={(event) => {
                      setNotes(event.target.value);
                      setError(null);
                    }}
                  />
                </ResponsiveLayout>
                {limitExceeded && (
                  <p role="alert" className="text-sm text-status-text-error-05">
                    {t("notesTooLong")}
                  </p>
                )}
              </>
            ) : (
              <>
                <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2">
                  {slideKinds.map((kind) => (
                    <Button
                      key={kind}
                      prominence="secondary"
                      disabled={!!busy || slides.length >= MAX_SLIDES}
                      onClick={() => add(kind)}
                    >
                      {t(
                        kind === "title"
                          ? "addTitle"
                          : kind === "points"
                            ? "addPoints"
                            : "addChart",
                      )}
                    </Button>
                  ))}
                </ResponsiveLayout>
                <ResponsiveLayout display="grid" className="min-w-0 gap-4 md:grid-cols-[10rem_minmax(0,1fr)]">
                  <nav
                    aria-label={t("slides")}
                    className="flex min-w-0 gap-1 overflow-x-auto pb-1 md:max-h-80 md:flex-col md:overflow-auto md:pb-0"
                  >
                    {slides.map((slide, position) => (
                      <ActionButton
                        key={slide.id}
                        type="button"
                        aria-current={slide.id === selectedId ? "step" : undefined}
                        className="max-w-40 shrink-0 truncate rounded-lg border border-border-01 px-3 py-2 text-start text-sm text-text-05 aria-[current=step]:border-blue-500 aria-[current=step]:bg-background-neutral-02 md:max-w-none"
                        onClick={() => setSelectedId(slide.id)}
                      >
                        {t("slideLabel", {
                          number: position + 1,
                          title: slide.title || t("untitled"),
                        })}
                      </ActionButton>
                    ))}
                  </nav>
                  <ResponsiveLayout display="grid" className="min-w-0 gap-3">
                    <figure
                      aria-label={t("preview")}
                      className={`grid aspect-video min-w-0 gap-2 overflow-auto rounded-xl p-4 sm:p-6 ${selected.kind === "title" ? "content-center bg-[#152744] text-white" : "grid-rows-[auto_minmax(0,1fr)] bg-[#f4f7fc] text-[#152744]"}`}
                    >
                      <figcaption className="min-w-0 break-words text-base font-semibold sm:text-2xl">
                        <span
                          aria-hidden="true"
                          className="mb-2 block h-1 w-9 rounded-full bg-[#6c91ef]"
                        />
                        {selected.title || t("untitled")}
                      </figcaption>
                      {selected.kind === "title" && selected.text && (
                        <p className="whitespace-pre-wrap break-words text-sm text-[#d5e3ff]">
                          {selected.text}
                        </p>
                      )}
                      {selected.kind === "points" && (
                        <ul className="grid content-start gap-1 overflow-auto ps-5 text-xs sm:text-sm">
                          {slidePoints(selected.text).map((point, pointIndex) => (
                            <li key={pointIndex} className="list-disc break-words">
                              {point}
                            </li>
                          ))}
                        </ul>
                      )}
                      {selected.kind === "chart" &&
                        (selected.image ? (
                          <img
                            src={selected.image.data}
                            alt={selected.image.name}
                            className="h-full min-h-0 w-full object-contain"
                          />
                        ) : (
                          <p className="place-self-center text-center text-2xs sm:text-sm">
                            {t("chartHint")}
                          </p>
                        ))}
                    </figure>
                    <ResponsiveLayout display="grid" className="gap-1 text-sm font-medium text-text-05">
                      <label htmlFor={titleId}>{t("slideTitle")}</label>
                      <NativeInput
                        id={titleId}
                        className={field}
                        maxLength={80}
                        value={selected.title}
                        onChange={(event) => edit(selected.id, { title: event.target.value })}
                      />
                    </ResponsiveLayout>
                    {selected.kind === "chart" ? (
                      <ResponsiveLayout display="grid" className="min-w-0 gap-1 text-sm text-text-05">
                        <label htmlFor={chartId} className="font-medium">
                          {t("attachChart")}
                        </label>
                        <NativeInput
                          id={chartId}
                          type="file"
                          accept="image/png,.png"
                          className="max-w-full"
                          disabled={!!busy}
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            event.target.value = "";
                            if (file) void attachChart(file);
                          }}
                        />
                        {busy === "image" && (
                          <output className="text-xs text-text-03">{t("reading")}</output>
                        )}
                        <p className="break-words text-xs text-text-03">
                          {selected.image?.name ?? t("chartHint")}
                        </p>
                      </ResponsiveLayout>
                    ) : (
                      <ResponsiveLayout display="grid" className="gap-1 text-sm font-medium text-text-05">
                        <label htmlFor={contentId}>
                          {t(selected.kind === "title" ? "subtitle" : "pointsLabel")}
                        </label>
                        <NativeTextArea
                          id={contentId}
                          className={field}
                          rows={selected.kind === "title" ? 2 : 5}
                          maxLength={selected.kind === "title" ? 180 : 600}
                          value={selected.text}
                          onChange={(event) => edit(selected.id, { text: event.target.value })}
                        />
                      </ResponsiveLayout>
                    )}
                    {selected.kind === "points" &&
                      slidePoints(selected.text).length > MAX_POINTS && (
                        <p role="alert" className="text-sm text-status-text-error-05">
                          {t("pointsLimit")}
                        </p>
                      )}
                    <ResponsiveLayout display="flex" className="flex-wrap gap-2">
                      <Button
                        prominence="tertiary"
                        disabled={!!busy || index === 0}
                        onClick={() => move(-1)}
                      >
                        {t("moveEarlier")}
                      </Button>
                      <Button
                        prominence="tertiary"
                        disabled={!!busy || index === slides.length - 1}
                        onClick={() => move(1)}
                      >
                        {t("moveLater")}
                      </Button>
                      <Button
                        prominence="tertiary"
                        disabled={!!busy || slides.length < 2}
                        onClick={remove}
                      >
                        {t("removeSlide")}
                      </Button>
                    </ResponsiveLayout>
                  </ResponsiveLayout>
                </ResponsiveLayout>
              </>
            )}
            {slides.length > 0 && (
              <OutputActions
                name={outputName}
                artifact={{
                  kind: "presentation",
                  payload: { slides: slides.map(({ id: _id, ...slide }) => slide) },
                }}
                saved={saved}
                disabled={!!busy}
              />
            )}
          </ResponsiveLayout>
        </Modal.Body>
        <Modal.Footer>
          {selected ? (
            <>
              {incomplete && <p className="text-xs text-text-03">{t("completeSlides")}</p>}
              <Button
                icon={SvgDownload}
                disabled={!!busy || incomplete}
                onClick={() => void download()}
              >
                {t(busy === "export" ? "exporting" : "download")}
              </Button>
            </>
          ) : (
            <Button disabled={!!busy || !notes.trim() || limitExceeded} onClick={create}>
              {t("create")}
            </Button>
          )}
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
