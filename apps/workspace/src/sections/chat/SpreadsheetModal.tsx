"use client";

import { outputFileName } from "@/lib/chat/outputs";
import { ResponsiveLayout } from "@opal/layouts";
import { ActionButton, NativeInput, NativeTextArea } from "@opal/components";
import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Modal } from "@opal/components";
import { SvgDownload, SvgPlus, SvgTrash } from "@opal/icons";
import { cn } from "@opal/utils";
import { downloadFile } from "@/lib/download";
import type { OutputLocation, SavedOutput } from "@/lib/chat/outputs";
import OutputActions from "./OutputActions";
import dynamic from "next/dynamic";

const Visualization = dynamic(() => import("./CsvVisualizationModal"), { loading: () => null });
import {
  SHEET_LIMITS,
  sheetColumnName,
  sheetFromCsv,
  sheetToCsv,
  sheetToXlsx,
} from "@/lib/chat/spreadsheet";

const PAGE_SIZE = 20;
const field =
  "rounded-md border border-border-02 bg-background-neutral-00 px-2 py-1 text-sm text-text-05";
const heading =
  "border border-border-01 bg-background-neutral-01 p-0 text-center text-xs text-text-04";
const coordinate =
  "block w-full px-2 py-1.5 hover:bg-background-neutral-02 aria-pressed:bg-background-neutral-03 aria-pressed:text-text-05";
const removeButton =
  "inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2 text-sm text-text-05 hover:bg-background-neutral-02 focus-visible:outline-2 disabled:opacity-50";

type Import = { rows: string[][]; name: string };
type ErrorKey = "fileTooLarge" | "invalidCsv" | "sheetTooLarge" | "exportFailed";

export default function SpreadsheetModal({
  onClose,
  saved,
}: {
  onClose: () => void;
  saved?: SavedOutput;
}) {
  const t = useTranslations("chat.spreadsheetBuilder");
  const fileId = useId();
  const nameId = useId();
  const [rows, setRows] = useState(() =>
    saved?.artifact.kind === "spreadsheet"
      ? saved.artifact.payload.rows
      : Array.from({ length: 5 }, () => Array<string>(4).fill("")),
  );
  const [name, setName] = useState(saved?.name ?? t("untitled"));
  const [savedOutput, setSavedOutput] = useState<OutputLocation | undefined>(saved);
  const [chart, setChart] = useState<{ text: string; name: string } | null>(null);
  const actions = useTranslations("chat.outputs");
  const [selected, setSelected] = useState({ row: 0, column: 0 });
  const [pendingImport, setPendingImport] = useState<Import | null>(null);
  const [busy, setBusy] = useState<"reading" | "exporting" | null>(null);
  const [error, setError] = useState<ErrorKey | null>(null);
  const columns = rows[0]!.length;
  const start = Math.floor(selected.row / PAGE_SIZE) * PAGE_SIZE;
  const end = Math.min(rows.length, start + PAGE_SIZE);
  const disabled = !!busy || !!pendingImport;
  const canAddRow =
    rows.length < SHEET_LIMITS.maxRows && (rows.length + 1) * columns <= SHEET_LIMITS.maxCells;
  const canAddColumn =
    columns < SHEET_LIMITS.maxColumns && rows.length * (columns + 1) <= SHEET_LIMITS.maxCells;

  const applyImport = (imported: Import) => {
    setRows(imported.rows);
    setName(imported.name);
    setSelected({ row: 0, column: 0 });
    setPendingImport(null);
  };

  const importFile = async (file: File) => {
    setError(null);
    if (!/\.csv$/i.test(file.name)) return setError("invalidCsv");
    if (file.size > SHEET_LIMITS.maxFileBytes) return setError("fileTooLarge");
    setBusy("reading");
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      const imported = {
        rows: sheetFromCsv(text),
        name: file.name.slice(0, -4).slice(0, 80) || t("untitled"),
      };
      if (rows.some((row) => row.some((cell) => cell !== ""))) setPendingImport(imported);
      else applyImport(imported);
    } catch (failure) {
      setError(failure instanceof RangeError ? "sheetTooLarge" : "invalidCsv");
    } finally {
      setBusy(null);
    }
  };

  const exportSheet = async (format: "csv" | "xlsx") => {
    setError(null);
    setBusy("exporting");
    const base = outputFileName(name, "")
      .replace(/\.(csv|xlsx)$/i, "")
      .replace(/[. ]+$/, "");
    const filename = `${base || t("untitled")}.${format}`;
    try {
      if (format === "csv") {
        downloadFile(filename, {
          content: `\uFEFF${sheetToCsv(rows)}`,
          mimeType: "text/csv;charset=utf-8",
        });
      } else {
        downloadFile(filename, { content: await sheetToXlsx(rows) });
      }
    } catch {
      setError("exportFailed");
    } finally {
      setBusy(null);
    }
  };

  const editCell = (row: number, column: number, text: string) => {
    setRows((current) =>
      current.map((record, index) =>
        index === row ? record.map((cell, index) => (index === column ? text : cell)) : record,
      ),
    );
  };

  if (chart) return <Visualization initialCsv={chart} onClose={() => setChart(null)} />;
  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="xl" maxHeight="92dvh">
        <Modal.Header title={t("title")} onClose={onClose} />
        <Modal.Body alignItems="stretch">
          <ResponsiveLayout display="flex" className="min-w-0 flex-col gap-3">
            <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-3">
              <ResponsiveLayout display="grid" className="min-w-0 gap-1">
                <label htmlFor={nameId} className="text-sm font-medium text-text-05">
                  {t("name")}
                </label>
                <NativeInput
                  id={nameId}
                  className={cn(field, "max-w-full")}
                  value={name}
                  maxLength={80}
                  disabled={disabled}
                  onChange={(event) => setName(event.target.value)}
                />
              </ResponsiveLayout>
              <ResponsiveLayout display="grid" className="min-w-0 gap-1">
                <label htmlFor={fileId} className="text-sm font-medium text-text-05">
                  {t("importCsv")}
                </label>
                <NativeInput
                  id={fileId}
                  type="file"
                  accept=".csv,text/csv"
                  disabled={disabled}
                  aria-describedby={`${fileId}-hint`}
                  className="w-full max-w-72 text-sm text-text-04"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) void importFile(file);
                  }}
                />
                <p id={`${fileId}-hint`} className="text-xs text-text-03">
                  {t("importHint")}
                </p>
              </ResponsiveLayout>
            </ResponsiveLayout>
            {busy && <output className="text-sm text-text-03">{t(busy)}</output>}
            {error && (
              <p role="alert" className="text-sm text-status-text-error-05">
                {t(error)}
              </p>
            )}
            {pendingImport && (
              <ResponsiveLayout display="flex" className="flex-wrap items-center gap-2 rounded-lg border border-border-02 p-2">
                <p role="status" className="text-sm text-text-05">
                  {t("replacePrompt", { name: pendingImport.name })}
                </p>
                <Button prominence="tertiary" onClick={() => setPendingImport(null)}>
                  {t("cancelImport")}
                </Button>
                <Button onClick={() => applyImport(pendingImport)}>{t("replace")}</Button>
              </ResponsiveLayout>
            )}
            <ResponsiveLayout display="flex" className="flex-wrap gap-1">
              <Button
                icon={SvgPlus}
                prominence="tertiary"
                disabled={disabled || !canAddRow}
                onClick={() => {
                  setRows([...rows, Array<string>(columns).fill("")]);
                  setSelected({ ...selected, row: rows.length });
                }}
              >
                {t("addRow")}
              </Button>
              <Button
                icon={SvgPlus}
                prominence="tertiary"
                disabled={disabled || !canAddColumn}
                onClick={() => {
                  setRows(rows.map((row) => [...row, ""]));
                  setSelected({ ...selected, column: columns });
                }}
              >
                {t("addColumn")}
              </Button>
              <ActionButton
                type="button"
                className={removeButton}
                disabled={disabled || rows.length === 1}
                onClick={() => {
                  setRows(rows.filter((_, index) => index !== selected.row));
                  setSelected({ ...selected, row: Math.min(selected.row, rows.length - 2) });
                }}
              >
                <SvgTrash className="size-4" aria-hidden="true" />
                {t("removeRow", { row: selected.row + 1 })}
              </ActionButton>
              <ActionButton
                type="button"
                className={removeButton}
                disabled={disabled || columns === 1}
                onClick={() => {
                  setRows(rows.map((row) => row.filter((_, index) => index !== selected.column)));
                  setSelected({ ...selected, column: Math.min(selected.column, columns - 2) });
                }}
              >
                <SvgTrash className="size-4" aria-hidden="true" />
                {t("removeColumn", { column: sheetColumnName(selected.column) })}
              </ActionButton>
            </ResponsiveLayout>
            {(!canAddRow || !canAddColumn) && (
              <p className="text-xs text-text-03">{t("gridLimit")}</p>
            )}
            <div className="min-w-0 overflow-x-auto rounded-lg border border-border-01">
              <table className="w-max min-w-full border-collapse">
                <caption className="sr-only">{t("grid")}</caption>
                <thead>
                  <tr>
                    <td className={heading} aria-hidden="true" />
                    {rows[0]!.map((_, column) => (
                      <th key={column} scope="col" className={heading}>
                        <ActionButton
                          type="button"
                          className={coordinate}
                          disabled={disabled}
                          aria-pressed={selected.column === column}
                          aria-label={t("selectColumn", { column: sheetColumnName(column) })}
                          onClick={() => setSelected({ ...selected, column })}
                        >
                          {sheetColumnName(column)}
                        </ActionButton>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(start, end).map((record, offset) => {
                    const row = start + offset;
                    return (
                      <tr key={row}>
                        <th scope="row" className={heading}>
                          <ActionButton
                            type="button"
                            className={coordinate}
                            disabled={disabled}
                            aria-pressed={selected.row === row}
                            aria-label={t("selectRow", { row: row + 1 })}
                            onClick={() => setSelected({ ...selected, row })}
                          >
                            {t("rowNumber", { row: row + 1 })}
                          </ActionButton>
                        </th>
                        {record.map((cell, column) => (
                          <td key={column} className="border border-border-01 p-0">
                            <NativeTextArea
                              rows={2}
                              maxLength={SHEET_LIMITS.maxCellLength}
                              spellCheck={false}
                              aria-label={t("cell", {
                                column: sheetColumnName(column),
                                row: row + 1,
                              })}
                              className={cn(
                                "block h-10 w-full min-w-28 resize-none bg-background-neutral-00 px-2 py-1 text-sm text-text-05 focus-visible:outline-2 focus-visible:-outline-offset-2",
                                selected.row === row &&
                                  selected.column === column &&
                                  "bg-background-neutral-01",
                              )}
                              value={cell}
                              disabled={disabled}
                              onFocus={() => setSelected({ row, column })}
                              onChange={(event) => editCell(row, column, event.target.value)}
                            />
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {rows.length > PAGE_SIZE && (
              <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-2">
                <output className="text-xs text-text-03">
                  {t("pageRows", { start: start + 1, end, total: rows.length })}
                </output>
                <ResponsiveLayout display="flex" className="gap-1">
                  <Button
                    prominence="tertiary"
                    disabled={disabled || start === 0}
                    onClick={() => setSelected({ ...selected, row: start - PAGE_SIZE })}
                  >
                    {t("previousRows")}
                  </Button>
                  <Button
                    prominence="tertiary"
                    disabled={disabled || end === rows.length}
                    onClick={() => setSelected({ ...selected, row: end })}
                  >
                    {t("nextRows")}
                  </Button>
                </ResponsiveLayout>
              </ResponsiveLayout>
            )}
            <OutputActions
              name={name.trim() || t("untitled")}
              artifact={{ kind: "spreadsheet", payload: { rows } }}
              saved={savedOutput}
              onSave={setSavedOutput}
              disabled={disabled}
            />
          </ResponsiveLayout>
        </Modal.Body>
        <Modal.Footer>
          <Button
            prominence="tertiary"
            disabled={disabled}
            onClick={() =>
              setChart({ text: sheetToCsv(rows), name: `${name.trim() || t("untitled")}.csv` })
            }
          >
            {actions("visualize")}
          </Button>
          <Button
            icon={SvgDownload}
            prominence="secondary"
            disabled={disabled}
            onClick={() => void exportSheet("csv")}
          >
            {t("downloadCsv")}
          </Button>
          <Button icon={SvgDownload} disabled={disabled} onClick={() => void exportSheet("xlsx")}>
            {t("downloadXlsx")}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
