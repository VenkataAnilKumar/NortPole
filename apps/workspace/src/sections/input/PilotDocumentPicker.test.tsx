import { NextIntlClientProvider } from "next-intl";
import messages from "@/i18n/messages/en.json";
import { fireEvent, render, screen } from "@testing-library/react";
import { PilotDocumentPicker } from "./PilotDocumentPicker";

afterEach(() => jest.restoreAllMocks());

test("searches the chosen library and returns the exact passage reference", async () => {
  const fetchSearch = jest.spyOn(global, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({ results: [{ id: "policy-2", chunk_id: 4, title: "Policy 2", excerpt: "Limit is six." }] }),
  } as Response);
  const onToggle = jest.fn();
  render(
    <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
      <PilotDocumentPicker libraries={[{ id: 7, name: "Policies" }, { id: 9, name: "Revisions" }]}
        selected={[]} onToggle={onToggle} disabled={false} />
    </NextIntlClientProvider>
  );

  fireEvent.click(screen.getByText("Select documents"));
  fireEvent.change(screen.getByLabelText("Knowledge library"), { target: { value: "9" } });
  fireEvent.change(screen.getByLabelText("Search library documents"), { target: { value: "policy" } });
  fireEvent.click(screen.getByText("Search"));
  fireEvent.click(await screen.findByRole("checkbox"));

  expect(fetchSearch).toHaveBeenCalledWith("/api/search/workspace", expect.objectContaining({
    body: JSON.stringify({ query: "policy", library_id: 9, page_size: 10 }),
  }));
  expect(onToggle).toHaveBeenCalledWith({ kind: "search-result", id: "policy-2", chunkId: 4, label: "Policy 2" });
});
