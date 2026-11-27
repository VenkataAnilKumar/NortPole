import { parseCsv, SPREADSHEET_PREVIEW_LIMITS } from "@/lib/csv";

export const SHEET_LIMITS = {
  maxRows: SPREADSHEET_PREVIEW_LIMITS.maxRows,
  maxColumns: SPREADSHEET_PREVIEW_LIMITS.maxColumns,
  maxCells: SPREADSHEET_PREVIEW_LIMITS.maxCells,
  maxFileBytes: SPREADSHEET_PREVIEW_LIMITS.maxCharacters,
  maxCellLength: 32_767,
};

export function sheetFromCsv(text: string) {
  const { maxRows, maxColumns, maxCells, maxCellLength } = SHEET_LIMITS;
  const { rows, truncated } = parseCsv(text, { maxRows, maxColumns, maxCells });
  const width = Math.max(1, ...rows.map((row) => row.length));
  if (
    truncated ||
    rows.length * width > maxCells ||
    rows.some((row) => row.some((cell) => cell.length > maxCellLength))
  ) {
    throw new RangeError("Spreadsheet exceeds editor limits");
  }
  return rows.length
    ? rows.map((row) => Array.from({ length: width }, (_, index) => row[index] ?? ""))
    : [[""]];
}

const plainNumber = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;
const csvNumber = /^[+-]?(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;
const formulaPrefix = /^[\s\p{Cc}\p{Cf}]*[=+\-@]/u;

export function sheetToCsv(rows: string[][]): string {
  return rows
    .map((row) =>
      row
        .map((cell) => {
          // Spreadsheet apps may evaluate formulas even in quoted CSV fields.
          const safe = formulaPrefix.test(cell) && !csvNumber.test(cell.trim()) ? `'${cell}` : cell;
          return /[",\r\n]/.test(safe) || (!safe && row.length === 1)
            ? `"${safe.replaceAll('"', '""')}"`
            : safe;
        })
        .join(","),
    )
    .join("\r\n");
}

function workbookValue(cell: string): string | number {
  if (!plainNumber.test(cell) || /^-0(?:\.0+)?$/.test(cell)) return cell;
  const digits = cell.replace(/[-.]/g, "").replace(/^0+/, "");
  // Excel preserves up to 15 significant digits. Keep longer IDs as text.
  if (digits.length > 15) return cell;
  const value = Number(cell);
  return digits && Math.abs(value) < 2.2250738585072014e-308 ? cell : value;
}

export async function sheetToXlsx(rows: string[][]): Promise<Blob> {
  const { utils, write } = await import("xlsx");
  const workbook = utils.book_new();
  const sheet = utils.aoa_to_sheet(rows.map((row) => row.map(workbookValue)));
  utils.book_append_sheet(workbook, sheet, "Sheet1");
  const bytes: ArrayBuffer = write(workbook, { bookType: "xlsx", type: "array" });
  return new Blob([bytes], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

export function sheetColumnName(index: number): string {
  return index < 26
    ? String.fromCharCode(65 + index)
    : sheetColumnName(Math.floor(index / 26) - 1) + sheetColumnName(index % 26);
}
