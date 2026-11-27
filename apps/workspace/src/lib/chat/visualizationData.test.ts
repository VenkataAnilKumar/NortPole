import {
  defaultChart,
  loadVisualizationData,
  summarizeColumn,
  visualizationPoints,
} from "./visualizationData";

test("plots numeric values without changing the CSV row order or treating blanks as zero", () => {
  const result = loadVisualizationData(
    '\uFEFFMonth,Revenue,Cost\r\n"North, Jan","1,250.50",-5\r\nFeb,0,0\r\nMar,,3\r\nApr,not available,4',
  );
  expect(result).toHaveProperty("dataset");
  if (!("dataset" in result)) throw new Error("Expected CSV data");
  expect(result.dataset.numericColumns).toEqual([1, 2]);
  expect(result.dataset.defaultLabel).toBe(0);
  expect(visualizationPoints(result.dataset, 0, 1)).toEqual([
    { label: "North, Jan", value: 1250.5 },
    { label: "Feb", value: 0 },
  ]);
  expect(visualizationPoints(result.dataset, 0, 2).map(({ value }) => value)).toEqual([
    -5, 0, 3, 4,
  ]);
});

test("rejects ambiguous headers, malformed rows, text-only data, and truncated CSVs", () => {
  expect(loadVisualizationData("Name,Name\nA,4")).toEqual({ error: "invalidHeaders" });
  expect(loadVisualizationData("Name,Value\nA,4,extra")).toEqual({ error: "malformed" });
  expect(loadVisualizationData('Name,Value\n"unclosed,4')).toEqual({ error: "malformed" });
  expect(loadVisualizationData("Name,Value\nA,0x10\nB,Infinity")).toEqual({ error: "noNumbers" });
  expect(loadVisualizationData("Name,Value\n" + "A,1\n".repeat(1001))).toEqual({
    error: "fileTooLarge",
  });
});

test("dashboard metrics use numeric cells, including zeros and negative values", () => {
  const result = loadVisualizationData(
    "Month,Revenue,Profit\nJan,15,-4\nFeb,0,6\nMar,22,10\nApr,,2",
  );
  if (!("dataset" in result)) throw new Error("Expected dashboard data");
  const { dataset } = result;
  expect(defaultChart(dataset, 0)).toEqual({ label: 0, value: 1, type: "bar" });
  expect(defaultChart(dataset, 1)).toEqual({ label: 0, value: 2, type: "bar" });
  expect(summarizeColumn(dataset, 1, "sum")).toBe(37);
  expect(summarizeColumn(dataset, 1, "count")).toBe(3);
  expect(summarizeColumn(dataset, 2, "average")).toBe(3.5);
  expect(summarizeColumn(dataset, 2, "minimum")).toBe(-4);
  expect(summarizeColumn(dataset, 2, "maximum")).toBe(10);
});
