import { xmlText } from "./xmlText";
import { unified } from "unified";
import remarkParse from "remark-parse";
import { documentLink } from "./documentDraft";

const parse = (body: string) => unified().use(remarkParse).parse(body);
type Block = ReturnType<typeof parse>["children"][number];
type Inline = Extract<Block, { type: "paragraph" }>["children"][number];

export async function documentDocx(name: string, body: string): Promise<Blob> {
  const {
    AlignmentType,
    Document,
    ExternalHyperlink,
    HeadingLevel,
    LevelFormat,
    Packer,
    Paragraph,
    TextRun,
  } = await import("docx");
  const headings = [
    HeadingLevel.HEADING_1,
    HeadingLevel.HEADING_2,
    HeadingLevel.HEADING_3,
    HeadingLevel.HEADING_4,
    HeadingLevel.HEADING_5,
    HeadingLevel.HEADING_6,
  ];
  type Run = InstanceType<typeof TextRun> | InstanceType<typeof ExternalHyperlink>;
  const blocks = parse(body).children;
  const definitions = new Map(
    blocks.flatMap((node) =>
      node.type === "definition" ? [[node.identifier, node.url] as const] : [],
    ),
  );
  const inline = (nodes: Inline[], bold = false, italics = false, style?: string): Run[] =>
    nodes.flatMap((node): Run[] => {
      if (node.type === "text" || node.type === "inlineCode")
        return [new TextRun({ text: xmlText(node.value), bold, italics, style })];
      if (node.type === "strong" || node.type === "emphasis")
        return inline(
          node.children,
          bold || node.type === "strong",
          italics || node.type === "emphasis",
          style,
        );
      if (node.type === "break") return [new TextRun({ break: 1 })];
      if (node.type === "link" || node.type === "linkReference") {
        const url = node.type === "link" ? node.url : definitions.get(node.identifier);
        const link = url ? documentLink(url) : null;
        const children = inline(node.children, bold, italics, link ? "Hyperlink" : style);
        if (!link) return children;
        return [
          new ExternalHyperlink({
            link,
            children,
          }),
        ];
      }
      if (node.type === "image" && node.alt) return [new TextRun(xmlText(node.alt))];
      return [];
    });

  const config: NonNullable<
    ConstructorParameters<typeof Document>[0]["numbering"]
  >["config"][number][] = [];
  type ParagraphValue = InstanceType<typeof Paragraph>;
  const render = (nodes: Block[], depth = 0): ParagraphValue[] =>
    nodes.flatMap((node) => {
      if (node.type === "paragraph" || node.type === "heading") {
        return [
          new Paragraph({
            children: inline(node.children),
            heading: node.type === "heading" ? headings[node.depth - 1] : undefined,
          }),
        ];
      }
      if (node.type === "list") {
        const reference = `list-${config.length}`;
        const indent = Math.min(depth, 8) * 360 + 600;
        config.push({
          reference,
          levels: [
            {
              level: 0,
              format: node.ordered ? LevelFormat.DECIMAL : LevelFormat.BULLET,
              text: node.ordered ? "%1." : "•",
              start: node.start ?? 1,
              alignment: AlignmentType.START,
              style: { paragraph: { indent: { left: indent, hanging: 360 } } },
            },
          ],
        });
        return node.children.flatMap(({ children }) => {
          const [first, ...remaining] = children;
          return first?.type === "paragraph"
            ? [
                new Paragraph({
                  children: inline(first.children),
                  numbering: { reference, level: 0 },
                }),
                ...render(remaining, depth + 1),
              ]
            : render(children, depth + 1);
        });
      }
      if (node.type === "blockquote") return render(node.children, depth);
      if (node.type === "code")
        return node.value.split("\n").map((line) => new Paragraph(xmlText(line)));
      return [];
    });
  const content = render(blocks);
  return Packer.toBlob(
    new Document({ title: xmlText(name), sections: [{ children: content }], numbering: { config } }),
  );
}
