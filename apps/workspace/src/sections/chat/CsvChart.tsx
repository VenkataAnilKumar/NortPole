"use client";

import { ResponsiveLayout } from "@opal/layouts";
import { NativeSelect } from "@opal/components";
import { useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  canPlot,
  type ChartPoint,
  type ChartSettings,
  type Dataset,
} from "@/lib/chat/visualizationData";

export const FIELD =
  "min-h-10 w-full rounded-lg border border-border-02 bg-background-neutral-00 px-2 text-sm text-text-05";
const SERIES = "#3b5ccc";
const TICKS = { fill: "#435168", fontSize: 11, fontFamily: "system-ui, sans-serif" };
const MARGIN = { top: 10, right: 12, bottom: 8, left: 0 };

export default function CsvChart({
  dataset,
  settings,
  points,
  onChange,
}: {
  dataset: Dataset;
  settings: ChartSettings;
  points: ChartPoint[];
  onChange: (settings: ChartSettings) => void;
}) {
  const t = useTranslations("chat.visualization");
  const locale = useLocale();
  const { label: labelColumn, value: valueColumn, type } = settings;
  const formatter = useMemo(
    () => new Intl.NumberFormat(locale, { maximumSignificantDigits: 12 }),
    [locale],
  );
  const tickFormatter = useMemo(
    () => new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 2 }),
    [locale],
  );
  const hasVisualizableValues = canPlot(points);
  const label = dataset.columns[labelColumn] ?? "";
  const value = dataset.columns[valueColumn] ?? "";
  const chartTitle = t("chartTitle", { value, label });
  const chartTypeName = t(type);
  const Chart = type === "bar" ? BarChart : LineChart;
  return (
    <ResponsiveLayout display="grid" className="min-w-0 gap-3">
      <ResponsiveLayout display="grid" className="min-w-0 gap-2 sm:grid-cols-3">
        <label className="grid min-w-0 gap-1 text-sm font-medium text-text-05">
          {t("labels")}
          <NativeSelect
            className={FIELD}
            aria-label={t("labels")}
            value={labelColumn}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (next === valueColumn) {
                const alternate = dataset.numericColumns.includes(labelColumn)
                  ? labelColumn
                  : dataset.numericColumns.find((column) => column !== next);
                if (alternate === undefined) return;
                onChange({ ...settings, label: next, value: alternate });
                return;
              }
              onChange({ ...settings, label: next });
            }}
          >
            {dataset.columns.map((column, index) => (
              <option
                key={column}
                value={index}
                disabled={index === valueColumn && dataset.numericColumns.length === 1}
              >
                {column}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid min-w-0 gap-1 text-sm font-medium text-text-05">
          {t("values")}
          <NativeSelect
            className={FIELD}
            aria-label={t("values")}
            value={valueColumn}
            onChange={(event) => {
              const next = Number(event.target.value);
              onChange({
                ...settings,
                value: next,
                label: next === labelColumn ? valueColumn : labelColumn,
              });
            }}
          >
            {dataset.numericColumns.map((index) => (
              <option key={index} value={index}>
                {dataset.columns[index]}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid min-w-0 gap-1 text-sm font-medium text-text-05">
          {t("chartType")}
          <NativeSelect
            className={FIELD}
            aria-label={t("chartType")}
            value={type}
            onChange={(event) =>
              onChange({ ...settings, type: event.target.value === "line" ? "line" : "bar" })
            }
          >
            <option value="bar">{t("bar")}</option>
            <option value="line">{t("line")}</option>
          </NativeSelect>
        </label>
      </ResponsiveLayout>
      {hasVisualizableValues ? (
        <>
          <figure
            aria-label={`${chartTitle} · ${chartTypeName}`}
            className="min-w-0 rounded-xl border border-border-01 bg-white p-3 text-[#17243b]"
          >
            <figcaption className="mb-2 break-words text-sm font-semibold">{chartTitle}</figcaption>
            <div
              data-export-title={chartTitle}
              data-export-axes={t("axes", { label, value })}
              dir="ltr"
              className="h-56 w-full sm:h-72"
              aria-hidden="true"
            >
              <ResponsiveContainer width="100%" height="100%">
                <Chart data={points} margin={MARGIN} accessibilityLayer={false}>
                  <CartesianGrid stroke="#e2e8f0" vertical={false} />
                  <XAxis
                    dataKey="label"
                    stroke="#64748b"
                    tick={TICKS}
                    minTickGap={16}
                    tickFormatter={(text: string) =>
                      text.length > 22 ? `${text.slice(0, 21)}…` : text
                    }
                  />
                  <YAxis
                    stroke="#64748b"
                    tick={TICKS}
                    width={52}
                    tickFormatter={(amount) => tickFormatter.format(amount)}
                    domain={[
                      (min: number) => Math.min(0, min),
                      (max: number) => Math.max(0, max) || 1,
                    ]}
                  />
                  <Tooltip
                    contentStyle={{ color: "#17243b" }}
                    formatter={(amount) => [formatter.format(Number(amount)), value]}
                  />
                  {type === "bar" ? (
                    <Bar dataKey="value" fill={SERIES} maxBarSize={48} isAnimationActive={false} />
                  ) : (
                    <Line
                      type="linear"
                      dataKey="value"
                      stroke={SERIES}
                      strokeWidth={2.5}
                      dot={points.length < 30 ? { fill: SERIES, r: 3 } : false}
                      isAnimationActive={false}
                    />
                  )}
                </Chart>
              </ResponsiveContainer>
            </div>
          </figure>
          <p className="text-xs text-text-03">
            {t("pointCount", {
              plotted: points.length,
              skipped: dataset.rows.length - points.length,
            })}
            {type === "line" && ` ${t("rowOrder")}`}
          </p>
          <details className="text-sm text-text-04">
            <summary className="cursor-pointer">{t("viewData")}</summary>
            <div className="mt-2 max-h-52 overflow-auto rounded-lg border border-border-01">
              <table className="w-full">
                <thead className="bg-background-neutral-01">
                  <tr>
                    <th scope="col" className="break-all p-2 text-start">
                      {label}
                    </th>
                    <th scope="col" className="break-all p-2 text-end">
                      {value}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((item, index) => (
                    <tr key={index} className="border-t border-border-01">
                      <td className="break-all p-2">{item.label}</td>
                      <td className="p-2 text-end tabular-nums">{formatter.format(item.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <p role="status" className="text-sm text-text-03">
          {t("noPoints")}
        </p>
      )}
    </ResponsiveLayout>
  );
}
