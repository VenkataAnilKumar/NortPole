import { deckFromNotes, MAX_NOTES_LENGTH, slidePoints } from "./presentation";

const labels = { title: "Untitled presentation", points: "Key points" };

test("preserves headings and content in an editable deck", () => {
  const deck = deckFromNotes(
    "# Operating plan\n\n## Progress\n- First milestone\n- Second milestone\n## Next\n1. Close the review",
    labels,
  );
  expect(deck).toEqual([
    { kind: "title", title: "Operating plan", text: "" },
    { kind: "points", title: "Progress", text: "First milestone\nSecond milestone" },
    { kind: "points", title: "Next", text: "Close the review" },
  ]);
});

test("splits long notes and overloaded sections into readable pages", () => {
  const long = "status ".repeat(40).trim();
  const content =
    "- " + long + "\n" + Array.from({ length: 6 }, (_, i) => "- Item " + i).join("\n");
  const deck = deckFromNotes(content, labels)!;
  expect(deck.length).toBeGreaterThan(2);
  const points = deck.slice(1).flatMap((slide) => slidePoints(slide.text));
  expect(deck.slice(1).every((slide) => slidePoints(slide.text).length <= 5)).toBe(true);
  expect(points.every((point) => point.length <= 120)).toBe(true);
  expect(points.join(" ")).toBe(long + " Item 0 Item 1 Item 2 Item 3 Item 4 Item 5");
  expect(deckFromNotes("x".repeat(MAX_NOTES_LENGTH + 1), labels)).toBe(null);
  expect(
    deckFromNotes(
      Array.from({ length: 24 }, (_, i) => "## Section " + i + "\n- Detail").join("\n"),
      labels,
    ),
  ).toBe(null);
});
