import { parseCsv } from "@/lib/csv";

export const MAX_CHART_FILE_BYTES = 2_000_000;

type DatasetError = "malformed" | "fileTooLarge" | "invalidHeaders" | "noNumbers";

export interface Dataset {
  columns: string[];
  rows: string[][];
  numericColumns: number[];
  defaultLabel: number;
}

const decimal = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;
const grouped = /^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$/;

function asNumber(cell: string | undefined): number | null {
  const text = cell?.trim() ?? "";
  if (!decimal.test(text) && !grouped.test(text)) return null;
  const number = Number(text.replaceAll(",", ""));
  return Number.isFinite(number) ? number : null;
}

export function loadVisualizationData(
  text: string,
): { dataset: Dataset } | { error: DatasetError } {
  let parsed: ReturnType<typeof parseCsv>;
  try {
    parsed = parseCsv(text, { maxRows: 1001, maxColumns: 100, maxCells: 50_000 });
  } catch {
    return { error: "malformed" };
  }
  if (parsed.truncated) return { error: "fileTooLarge" };
  const [header = [], ...records] = parsed.rows;
  const columns = header.map((cell) => cell.trim());
  if (
    columns.length < 2 ||
    columns.some((name) => !name) ||
    new Set(columns).size !== columns.length
  ) {
    return { error: "invalidHeaders" };
  }
  const rows = records.filter((row) => row.some((cell) => cell.trim()));
  if (rows.some((row) => row.length > columns.length)) return { error: "malformed" };
  const numericColumns = columns.flatMap((_, index) =>
    rows.some((row) => asNumber(row[index]) !== null) ? [index] : [],
  );
  if (!numericColumns.length) return { error: "noNumbers" };
  const defaultLabel = columns.findIndex((_, index) => !numericColumns.includes(index));
  return {
    dataset: {
      columns,
      rows,
      numericColumns,
      defaultLabel: defaultLabel === -1 ? 0 : defaultLabel,
    },
  };
}

export interface ChartPoint {
  label: string;
  value: number;
}

export interface ChartSettings {
  label: number;
  value: number;
  type: "bar" | "line";
}

export function defaultChart(dataset: Dataset, index = 0): ChartSettings {
  const values = dataset.numericColumns.filter((column) => column !== dataset.defaultLabel);
  const candidates = values.length ? values : dataset.numericColumns;
  const value = candidates[index % candidates.length]!;
  return {
    type: "bar",
    value,
    label: value === dataset.defaultLabel ? (value === 0 ? 1 : 0) : dataset.defaultLabel,
  };
}

export function canPlot(points: ChartPoint[]): boolean {
  if (!points.length) return false;
  const values = points.map(({ value }) => value);
  return Number.isFinite(Math.max(0, ...values) - Math.min(0, ...values));
}

export const METRIC_OPERATIONS = ["sum", "average", "minimum", "maximum", "count"] as const;
export type MetricOperation = (typeof METRIC_OPERATIONS)[number];

export function summarizeColumn(
  dataset: Dataset,
  column: number,
  operation: MetricOperation,
): number | null {
  const values = dataset.rows.flatMap((row) => {
    const value = asNumber(row[column]);
    return value === null ? [] : [value];
  });
  if (operation === "count") return values.length;
  if (!values.length) return null;
  if (operation === "minimum") return Math.min(...values);
  if (operation === "maximum") return Math.max(...values);
  const divisor = operation === "average" ? values.length : 1;
  const result = values.reduce((total, value) => total + value / divisor, 0);
  return Number.isFinite(result) ? result : null;
}

export function visualizationPoints(
  dataset: Dataset,
  labelColumn: number,
  valueColumn: number,
): ChartPoint[] {
  return dataset.rows.flatMap((row) => {
    const label = row[labelColumn]?.trim().replace(/\s+/g, " ");
    const value = asNumber(row[valueColumn]);
    return label && value !== null ? [{ label, value }] : [];
  });
}
