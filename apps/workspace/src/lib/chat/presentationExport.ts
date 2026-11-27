import { slidePoints, type Slide } from "./presentation";

import { xmlText } from "./xmlText";

export async function presentationPptx(slides: Slide[]): Promise<Blob> {
  const { default: PptxGenJS } = await import("pptxgenjs");
  const deck = new PptxGenJS();
  deck.layout = "LAYOUT_WIDE";
  deck.title = xmlText(slides[0]?.title || "") || "Presentation";
  const navy = "152744";
  const blue = "4870D4";
  const muted = "425575";
  const fontFace = "Aptos";

  for (const item of slides) {
    const slide = deck.addSlide();
    const cover = item.kind === "title";
    slide.background = { color: cover ? navy : "F4F7FC" };
    slide.addShape(deck.ShapeType.rect, {
      x: 0.65,
      y: cover ? 1.52 : 0.48,
      w: 0.64,
      h: 0.075,
      fill: { color: cover ? "8CACFF" : blue },
      line: { transparency: 100 },
    });
    slide.addText(xmlText(item.title), {
      x: 0.65,
      y: cover ? 1.83 : 0.72,
      w: 12,
      h: cover ? 2 : 1,
      margin: 0,
      fontFace,
      fontSize: cover ? 46 : 31,
      bold: true,
      color: cover ? "FFFFFF" : navy,
      fit: "shrink",
      valign: "middle",
    });
    if (cover && item.text) {
      slide.addText(xmlText(item.text), {
        x: 0.65,
        y: 4.1,
        w: 11.8,
        h: 1.35,
        margin: 0,
        fontFace,
        fontSize: 23,
        color: "D5E3FF",
        fit: "shrink",
      });
    }
    if (item.kind === "points") {
      const points = slidePoints(xmlText(item.text));
      points.forEach((text, index) => {
        slide.addText(text, {
          x: 0.85,
          y: 1.86 + index * 0.99,
          w: 11.35,
          h: 0.86,
          margin: 0.05,
          fontFace,
          fontSize: 23,
          color: muted,
          bullet: { indent: 25 },
          fit: "shrink",
          valign: "middle",
        });
      });
    }
    if (item.kind === "chart" && item.image) {
      const { data, width, height } = item.image;
      const scale = Math.min(12 / width, 5.24 / height);
      const w = width * scale;
      const h = height * scale;
      slide.addImage({ data, x: 0.65 + (12 - w) / 2, y: 1.77 + (5.24 - h) / 2, w, h });
    }
  }

  const bytes = await deck.write({ outputType: "arraybuffer" });
  return new Blob([bytes as ArrayBuffer], {
    type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  });
}
