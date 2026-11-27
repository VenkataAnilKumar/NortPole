interface Metric {
  label: string;
  value: string;
}

async function snapshot(element: HTMLElement) {
  const svg = element.querySelector<SVGSVGElement>("svg.recharts-surface");
  if (!svg) throw new Error("Chart is not visible");
  const { width, height } = svg.getBoundingClientRect();
  if (width <= 0 || height <= 0) throw new Error("Chart is not visible");

  const copy = svg.cloneNode(true) as SVGSVGElement;
  copy.setAttribute("width", String(width));
  copy.setAttribute("height", String(height));
  const url = URL.createObjectURL(
    new Blob([new XMLSerializer().serializeToString(copy)], {
      type: "image/svg+xml;charset=utf-8",
    }),
  );
  const image = new Image();
  try {
    image.src = url;
    await image.decode();
    return {
      image,
      width,
      height,
      title: element.dataset.exportTitle ?? "",
      axes: element.dataset.exportAxes ?? "",
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function visualizationPng(
  container: HTMLElement,
  dashboard?: {
    title: string;
    file: string;
    metrics: Metric[];
  },
): Promise<Blob> {
  const plots = Array.from(container.querySelectorAll<HTMLElement>("[data-export-title]"));
  if (!plots.length) throw new Error("Chart is not visible");
  const charts = await Promise.all(plots.map(snapshot));
  const width = Math.max(...charts.map((chart) => chart.width)) + 32;
  const metricColumns = width >= 520 ? 2 : 1;
  const headerHeight = dashboard
    ? 72 + Math.ceil(dashboard.metrics.length / metricColumns) * 66
    : 0;
  const height = headerHeight + charts.reduce((total, chart) => total + chart.height + 100, 0);

  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(width * 2);
  canvas.height = Math.ceil(height * 2);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas is unavailable");
  context.scale(2, 2);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);

  const heading = (text: string, x: number, y: number, available: number) => {
    context.font = "600 18px system-ui, sans-serif";
    context.fillStyle = "#17243b";
    context.fillText(text, x, y, available);
  };
  const caption = (text: string, x: number, y: number, available: number) => {
    context.font = "13px system-ui, sans-serif";
    context.fillStyle = "#435168";
    context.fillText(text, x, y, available);
  };
  if (dashboard) {
    heading(dashboard.title, 16, 30, width - 32);
    caption(dashboard.file, 16, 51, width - 32);
    const metricWidth = (width - 24) / metricColumns;
    dashboard.metrics.forEach((metric, index) => {
      const x = 12 + (index % metricColumns) * metricWidth;
      const y = 68 + Math.floor(index / metricColumns) * 66;
      context.fillStyle = "#f0f3ff";
      context.fillRect(x, y, metricWidth - 8, 56);
      caption(metric.label, x + 10, y + 19, metricWidth - 28);
      heading(metric.value, x + 10, y + 43, metricWidth - 28);
    });
  }

  let y = headerHeight;
  for (const chart of charts) {
    heading(chart.title, 16, y + 30, width - 32);
    caption(chart.axes, 16, y + 51, width - 32);
    context.drawImage(chart.image, 16, y + 74, chart.width, chart.height);
    y += chart.height + 100;
  }
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("PNG could not be encoded"))),
      "image/png",
    );
  });
}
