import { read } from "xlsx";
import {
  SHEET_LIMITS,
  sheetColumnName,
  sheetFromCsv,
  sheetToCsv,
  sheetToXlsx,
} from "./spreadsheet";

test("preserves multiline values, identifiers and empty cells from a ragged CSV", () => {
  const rows = sheetFromCsv('\uFEFFCode,Notes\r\n00123,"two lines\r\nand a ""quote"""\r\n4\r\n');
  expect(rows).toEqual([
    ["Code", "Notes"],
    ["00123", 'two lines\r\nand a "quote"'],
    ["4", ""],
  ]);
  expect(sheetFromCsv(sheetToCsv(rows))).toEqual(rows);
  expect(sheetFromCsv(sheetToCsv([[""], [""], [""]]))).toEqual([[""], [""], [""]]);
});

test("accepts the exact grid limit and rejects oversize, ragged and malformed data", () => {
  const wideRow = Array<string>(SHEET_LIMITS.maxColumns).fill("x").join(",");
  expect(sheetFromCsv(Array<string>(50).fill(wideRow).join("\r\n"))).toHaveLength(50);
  expect(() => sheetFromCsv(`${wideRow}\n${"x\n".repeat(50)}`)).toThrow(RangeError);
  expect(() => sheetFromCsv(`${wideRow},overflow`)).toThrow(RangeError);
  expect(() => sheetFromCsv("x".repeat(SHEET_LIMITS.maxCellLength + 1))).toThrow(RangeError);
  expect(() => sheetFromCsv('x,"unterminated')).toThrow("Malformed CSV");
});

test("quotes formula-like CSV strings and preserves numeric values", () => {
  const cells = ["=SUM(A1)", "\t@NOW()", "-hold", "+draft", "-42", "+7.50", "-1,000"];
  expect(sheetFromCsv(sheetToCsv([cells]))).toEqual([
    ["'=SUM(A1)", "'\t@NOW()", "'-hold", "'+draft", "-42", "+7.50", "-1,000"],
  ]);
});

test("writes a workbook with numbers and literal identifiers and formula-like text", async () => {
  const tiny = `0.${"0".repeat(500)}1`;
  const blob = await sheetToXlsx([["-42", "7.50", "0012", "1234567890123456", "=1+1", tiny]]);
  const sheet = read(await blob.arrayBuffer(), { type: "array" }).Sheets.Sheet1!;
  expect(sheet.A1).toMatchObject({ t: "n", v: -42 });
  expect(sheet.B1).toMatchObject({ t: "n", v: 7.5 });
  expect(sheet.C1).toMatchObject({ t: "s", v: "0012" });
  expect(sheet.D1).toMatchObject({ t: "s", v: "1234567890123456" });
  expect(sheet.E1).toMatchObject({ t: "s", v: "=1+1" });
  expect(sheet.E1).not.toHaveProperty("f");
  expect(sheet.F1).toMatchObject({ t: "s", v: tiny });
});

test("labels columns beyond Z", () => {
  expect([0, 25, 26, 51, 52, 99].map(sheetColumnName)).toEqual(["A", "Z", "AA", "AZ", "BA", "CV"]);
});
