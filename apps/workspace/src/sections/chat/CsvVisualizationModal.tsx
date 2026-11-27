"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeInput, NativeSelect } from "@opal/components";
import { useId, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { Button, Modal } from "@opal/components";
import { SvgDownload, SvgPlus, SvgX } from "@opal/icons";
import { downloadFile } from "@/lib/download";
import {
  canPlot,
  defaultChart,
  loadVisualizationData,
  MAX_CHART_FILE_BYTES,
  METRIC_OPERATIONS,
  summarizeColumn,
  visualizationPoints,
  type ChartSettings,
  type MetricOperation,
  type Dataset,
} from "@/lib/chat/visualizationData";
import { visualizationPng } from "@/lib/chat/visualizationPng";
import { presentationChart } from "@/lib/chat/presentationFiles";
import type { ChartImage } from "@/lib/chat/presentation";
import CsvChart, { FIELD } from "./CsvChart";

type DatasetError = Extract<ReturnType<typeof loadVisualizationData>, { error: string }>["error"];
type ErrorKey = DatasetError | "unsupportedFile" | "readFailed" | "exportFailed";
type Chart = ChartSettings & { id: number };
type Metric = { id: number; column: number; operation: MetricOperation };

const WIDGET_LIMIT = 4;
const Presentation = dynamic(() => import("./PresentationModal"), { loading: () => null });

export default function CsvVisualizationModal({
  onClose,
  mode = "chart",
  initialCsv,
}: {
  onClose: () => void;
  mode?: "chart" | "dashboard";
  initialCsv?: { text: string; name: string };
}) {
  const t = useTranslations("chat.visualization");
  const d = useTranslations("chat.dashboardBuilder");
  const actions = useTranslations("chat.outputs");
  const locale = useLocale();
  const uploadId = useId();
  const plot = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);
  const [initial] = useState(() => {
    if (!initialCsv) return null;
    if (new TextEncoder().encode(initialCsv.text).length > MAX_CHART_FILE_BYTES)
      return { error: "fileTooLarge" as const };
    const result = loadVisualizationData(initialCsv.text);
    return "error" in result ? result : { ...result, name: initialCsv.name };
  });
  const [loaded, setLoaded] = useState<{ dataset: Dataset; name: string } | null>(
    initial && "dataset" in initial ? initial : null,
  );
  const [charts, setCharts] = useState<Chart[]>(() =>
    loaded ? [{ ...defaultChart(loaded.dataset), id: 1 }] : [],
  );
  const [metrics, setMetrics] = useState<Metric[]>(() =>
    loaded ? [{ id: 1, column: defaultChart(loaded.dataset).value, operation: "sum" }] : [],
  );
  const [reading, setReading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(
    initial && "error" in initial ? initial.error : null,
  );
  const [chartImage, setChartImage] = useState<ChartImage | null>(null);
  const isDashboard = mode === "dashboard";

  const chooseFile = async (file: File) => {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("unsupportedFile");
      return;
    }
    if (file.size > MAX_CHART_FILE_BYTES) {
      setError("fileTooLarge");
      return;
    }
    setReading(true);
    try {
      const decoded = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      const result = loadVisualizationData(decoded);
      if ("error" in result) {
        setError(result.error);
        return;
      }
      const initial = defaultChart(result.dataset);
      setLoaded({ ...result, name: file.name });
      setCharts([{ ...initial, id: ++nextId.current }]);
      setMetrics([{ id: ++nextId.current, column: initial.value, operation: "sum" }]);
    } catch {
      setError("readFailed");
    } finally {
      setReading(false);
    }
  };

  const dataset = loaded?.dataset;
  const formatter = useMemo(
    () => new Intl.NumberFormat(locale, { maximumSignificantDigits: 12 }),
    [locale],
  );
  const chartPoints = useMemo(
    () =>
      dataset ? charts.map(({ label, value }) => visualizationPoints(dataset, label, value)) : [],
    [dataset, charts],
  );
  const metricValues = useMemo(
    () =>
      dataset && isDashboard
        ? metrics.map(({ column, operation }) => summarizeColumn(dataset, column, operation))
        : [],
    [dataset, isDashboard, metrics],
  );
  const dashboardMetrics =
    dataset && isDashboard
      ? metrics.map(({ column, operation }, index) => ({
          label: d("metricSummary", { operation: d(operation), column: dataset.columns[column]! }),
          value:
            metricValues[index] == null ? d("unavailable") : formatter.format(metricValues[index]!),
        }))
      : [];
  const canExport = chartPoints.length > 0 && chartPoints.every(canPlot);

  const exportPng = async (useInPresentation = false) => {
    if (!plot.current || !loaded || !canExport) return;
    setError(null);
    setExporting(true);
    try {
      const png = await visualizationPng(
        plot.current,
        isDashboard
          ? {
              title: d("dashboard"),
              file: loaded.name,
              metrics: dashboardMetrics,
            }
          : undefined,
      );
      const filename = `${loaded.name.replace(/\.csv$/i, "")}-${mode}.png`;
      if (useInPresentation)
        setChartImage(await presentationChart(new File([png], filename, { type: "image/png" })));
      else downloadFile(filename, { content: png });
    } catch {
      setError("exportFailed");
    } finally {
      setExporting(false);
    }
  };

  if (chartImage)
    return <Presentation initialChart={chartImage} onClose={() => setChartImage(null)} />;
  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="lg" maxHeight="92dvh" preventAccidentalClose={false}>
        <Modal.Header title={isDashboard ? d("title") : t("title")} onClose={onClose} />
        <Modal.Body alignItems="stretch">
          <ResponsiveLayout display="flex" className="min-w-0 flex-col gap-4">
            <ResponsiveLayout display="flex" className="flex-wrap items-start justify-between gap-3 rounded-xl border border-border-01 p-3">
              <ResponsiveLayout display="grid" className="min-w-0 gap-1">
                <label htmlFor={uploadId} className="text-sm font-semibold text-text-05">
                  {t("attach")}
                </label>
                <NativeInput
                  id={uploadId}
                  type="file"
                  accept=".csv,text/csv"
                  disabled={reading || exporting}
                  className="max-w-full text-sm text-text-04"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) void chooseFile(file);
                  }}
                />
                <p className="break-all text-xs text-text-03">{loaded?.name ?? t("fileHint")}</p>
              </ResponsiveLayout>
              {reading && <output className="text-sm text-text-03">{t("reading")}</output>}
            </ResponsiveLayout>
            {error && (
              <p role="alert" className="text-sm text-status-text-error-05">
                {t(error)}
              </p>
            )}
            {dataset && (
              <ResponsiveLayout display="grid" ref={plot} className="min-w-0 gap-4">
                {isDashboard && (
                  <section aria-label={d("metrics")} className="grid min-w-0 gap-3">
                    <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-2">
                      <h2 className="font-semibold text-text-05">{d("metrics")}</h2>
                      <Button
                        icon={SvgPlus}
                        prominence="secondary"
                        disabled={metrics.length >= WIDGET_LIMIT}
                        onClick={() => {
                          const id = ++nextId.current;
                          setMetrics((current) => [
                            ...current,
                            {
                              id,
                              column: defaultChart(dataset, current.length).value,
                              operation: "sum",
                            },
                          ]);
                        }}
                      >
                        {d("addMetric")}
                      </Button>
                    </ResponsiveLayout>
                    <ResponsiveLayout display="grid" className="min-w-0 gap-3 sm:grid-cols-2">
                      {metrics.map((metric, index) => (
                        <article
                          key={metric.id}
                          aria-label={d("metricNumber", { number: index + 1 })}
                          className="min-w-0 rounded-xl border border-border-01 bg-background-neutral-01 p-3"
                        >
                          <ResponsiveLayout display="flex" className="min-w-0 items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="break-words text-sm font-medium text-text-04">
                                {dashboardMetrics[index]?.label}
                              </p>
                              <p className="break-all text-2xl font-semibold tabular-nums text-text-05">
                                {dashboardMetrics[index]?.value}
                              </p>
                            </div>
                            {metrics.length > 1 && (
                              <Button
                                icon={SvgX}
                                prominence="tertiary"
                                aria-label={d("removeMetric")}
                                onClick={() =>
                                  setMetrics((current) =>
                                    current.filter(({ id }) => id !== metric.id),
                                  )
                                }
                              />
                            )}
                          </ResponsiveLayout>
                          <ResponsiveLayout display="grid" className="mt-3 min-w-0 grid-cols-2 gap-2">
                            <label className="grid min-w-0 gap-1 text-sm text-text-04">
                              {d("column")}
                              <NativeSelect
                                className={FIELD}
                                aria-label={d("column")}
                                value={metric.column}
                                onChange={(event) => {
                                  const column = Number(event.target.value);
                                  setMetrics((current) =>
                                    current.map((item) =>
                                      item.id === metric.id ? { ...item, column } : item,
                                    ),
                                  );
                                }}
                              >
                                {dataset.numericColumns.map((column) => (
                                  <option key={column} value={column}>
                                    {dataset.columns[column]}
                                  </option>
                                ))}
                              </NativeSelect>
                            </label>
                            <label className="grid min-w-0 gap-1 text-sm text-text-04">
                              {d("calculation")}
                              <NativeSelect
                                className={FIELD}
                                aria-label={d("calculation")}
                                value={metric.operation}
                                onChange={(event) => {
                                  const operation = event.target.value as MetricOperation;
                                  setMetrics((current) =>
                                    current.map((item) =>
                                      item.id === metric.id ? { ...item, operation } : item,
                                    ),
                                  );
                                }}
                              >
                                {METRIC_OPERATIONS.map((operation) => (
                                  <option key={operation} value={operation}>
                                    {d(operation)}
                                  </option>
                                ))}
                              </NativeSelect>
                            </label>
                          </ResponsiveLayout>
                        </article>
                      ))}
                    </ResponsiveLayout>
                  </section>
                )}
                {isDashboard && (
                  <ResponsiveLayout display="flex" className="flex-wrap items-center justify-between gap-2">
                    <h2 className="font-semibold text-text-05">{d("charts")}</h2>
                    <Button
                      icon={SvgPlus}
                      prominence="secondary"
                      disabled={charts.length >= WIDGET_LIMIT}
                      onClick={() => {
                        const id = ++nextId.current;
                        setCharts((current) => [
                          ...current,
                          { ...defaultChart(dataset, current.length), id },
                        ]);
                      }}
                    >
                      {d("addChart")}
                    </Button>
                  </ResponsiveLayout>
                )}
                {charts.map((chart, index) => (
                  <section
                    key={chart.id}
                    aria-label={isDashboard ? d("chartNumber", { number: index + 1 }) : undefined}
                    className={
                      isDashboard
                        ? "grid min-w-0 gap-3 rounded-xl border border-border-01 p-3"
                        : "min-w-0"
                    }
                  >
                    {isDashboard && charts.length > 1 && (
                      <ResponsiveLayout display="flex" className="justify-end">
                        <Button
                          icon={SvgX}
                          prominence="tertiary"
                          aria-label={d("removeChart")}
                          onClick={() =>
                            setCharts((current) => current.filter(({ id }) => id !== chart.id))
                          }
                        />
                      </ResponsiveLayout>
                    )}
                    <CsvChart
                      dataset={dataset}
                      settings={chart}
                      points={chartPoints[index] ?? []}
                      onChange={(settings) =>
                        setCharts((current) =>
                          current.map((item) =>
                            item.id === chart.id ? { ...settings, id: item.id } : item,
                          ),
                        )
                      }
                    />
                  </section>
                ))}
              </ResponsiveLayout>
            )}
          </ResponsiveLayout>
        </Modal.Body>
        {loaded && (
          <Modal.Footer>
            <Button
              prominence="secondary"
              disabled={!canExport || exporting || reading}
              onClick={() => void exportPng(true)}
            >
              {actions("usePresentation")}
            </Button>
            <Button
              icon={SvgDownload}
              onClick={() => void exportPng()}
              disabled={!canExport || exporting || reading}
            >
              {t(exporting ? "exporting" : "download")}
            </Button>
          </Modal.Footer>
        )}
      </Modal.Content>
    </Modal>
  );
}
