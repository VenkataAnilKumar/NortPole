import { MAX_NOTES_LENGTH, type ChartImage } from "./presentation";

export const MAX_DOCUMENT_BYTES = 5_000_000;
export const MAX_PNG_BYTES = 10_000_000;
export const SOURCE_EXTENSIONS = /\.(pdf|docx|md|txt)$/i;
const MAX_PDF_PAGES = 30;

function checkNotes(text: string): string {
  const notes = text.replace(/\r\n?/g, "\n").trim();
  if (notes.length > MAX_NOTES_LENGTH) throw new RangeError("Notes are too long");
  if (!notes) throw new Error("No readable text");
  return notes;
}

async function docxNotes(file: File): Promise<string> {
  const { BlobReader, TextWriter, ZipReader } = await import("@zip.js/zip.js");
  const archive = new ZipReader(new BlobReader(file));
  try {
    const entry = (await archive.getEntries()).find(
      (item) => item.filename === "word/document.xml",
    );
    if (!entry || entry.directory || entry.uncompressedSize > 2_000_000)
      throw new Error("Unsupported document");
    const xml = new DOMParser().parseFromString(
      await entry.getData(new TextWriter()),
      "application/xml",
    );
    if (xml.querySelector("parsererror")) throw new Error("Bad document XML");
    const namespace = xml.documentElement.namespaceURI;
    if (!namespace) throw new Error("Missing document namespace");
    return checkNotes(
      Array.from(xml.getElementsByTagNameNS(namespace, "p"))
        .map((paragraph) => {
          const text = Array.from(paragraph.getElementsByTagNameNS(namespace, "t"))
            .map((run) => run.textContent ?? "")
            .join("");
          const style = paragraph
            .getElementsByTagNameNS(namespace, "pStyle")[0]
            ?.getAttributeNS(namespace, "val");
          if (style?.toLowerCase() === "title" && text.trim()) return `# ${text}`;
          return style && /^heading\d+$/i.test(style) && text.trim() ? `## ${text}` : text;
        })
        .join("\n"),
    );
  } finally {
    await archive.close();
  }
}

async function pdfNotes(file: File): Promise<string> {
  const pdfjs = await import("pdfjs-dist");
  const assetRoot = `/pdfjs/${pdfjs.version}/`;
  pdfjs.GlobalWorkerOptions.workerSrc = `${assetRoot}pdf.worker.min.mjs`;
  const loading = pdfjs.getDocument({
    data: new Uint8Array(await file.arrayBuffer()),
    cMapUrl: `${assetRoot}cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `${assetRoot}standard_fonts/`,
    wasmUrl: `${assetRoot}wasm/`,
  });
  try {
    const pdf = await loading.promise;
    if (pdf.numPages > MAX_PDF_PAGES) throw new RangeError("PDF is too long");
    let notes = "";
    for (let number = 1; number <= pdf.numPages; number++) {
      const page = await pdf.getPage(number);
      const { items } = await page.getTextContent();
      notes +=
        items.map((item) => ("str" in item ? item.str + (item.hasEOL ? "\n" : " ") : "")).join("") +
        "\n";
      if (notes.length > MAX_NOTES_LENGTH) throw new RangeError("Notes are too long");
    }
    return checkNotes(notes);
  } finally {
    await loading.destroy();
  }
}

export async function presentationNotes(file: File): Promise<string> {
  const name = file.name.toLowerCase();
  if (!SOURCE_EXTENSIONS.test(name) || file.size > MAX_DOCUMENT_BYTES) {
    throw new Error("Unsupported attachment");
  }
  if (name.endsWith(".docx")) return docxNotes(file);
  if (name.endsWith(".pdf")) return pdfNotes(file);
  return checkNotes(new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer()));
}

export async function presentationChart(file: File): Promise<ChartImage> {
  if (!file.name.toLowerCase().endsWith(".png") || file.size > MAX_PNG_BYTES) {
    throw new Error("Unsupported image");
  }
  const header = new Uint8Array(await file.slice(0, 24).arrayBuffer());
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  const view = new DataView(header.buffer);
  if (
    header.length !== 24 ||
    !signature.every((byte, index) => header[index] === byte) ||
    view.getUint32(16) * view.getUint32(20) > 32_000_000
  ) {
    throw new Error("Unsupported PNG");
  }
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      typeof reader.result === "string"
        ? resolve(reader.result)
        : reject(new Error("Image unreadable"));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(new Blob([file], { type: "image/png" }));
  });
  const image = new Image();
  image.src = data;
  await image.decode();
  return { name: file.name, data, width: image.naturalWidth, height: image.naturalHeight };
}
