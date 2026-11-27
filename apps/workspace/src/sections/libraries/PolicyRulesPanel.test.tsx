import { fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/i18n/messages/en.json";
import PolicyRulesPanel from "./PolicyRulesPanel";

afterEach(() => jest.restoreAllMocks());

test("saves a threshold comparison and restores it when editing the rule", async () => {
  function result(payload: object) {
    return { ok: true, json: async () => payload } as Response;
  }

  const endpoint = "/api/manage/admin/document-set/7/policy-rules";
  const excerpt = "Receipts are required for expenses above 25 dollars.";
  const fetch = jest.spyOn(global, "fetch").mockImplementation(async (url, init) => {
    if (url === "/api/search/workspace") {
      return result({ results: [{ id: "policy", chunk_id: 2, title: "Travel policy", excerpt }] });
    }
    if (url === endpoint && init?.method === "POST") {
      return result({ id: "rule", source_title: "Travel policy", rule: JSON.parse(String(init.body)) });
    }
    return result({ enabled: true, rules: [] });
  });
  const { container } = render(
    <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
      <PolicyRulesPanel id={7} name="Policies" />
    </NextIntlClientProvider>
  );

  const disclosure = container.querySelector("details")!;
  disclosure.open = true;
  fireEvent(disclosure, new Event("toggle"));
  fireEvent.click(await screen.findByRole("button", { name: "Add rule" }));

  const question = "Does an expense of ${amount} meet the receipt threshold?";
  for (const [label, value] of [
    ["Threshold comparison", "gt"],
    ["Complete questions, one per line", question],
    ["Action", "Attach receipt"],
    ["Answer field", "threshold"],
    ["Answer", "25"],
    ["Unit (optional)", "dollars"],
    ["Exact source excerpt containing the answer and unit", excerpt],
  ] as const) {
    fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } });
  }

  fireEvent.click(screen.getByText("Select documents"));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search library documents" }), {
    target: { value: "Travel policy" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Travel policy" }));
  fireEvent.click(screen.getByRole("button", { name: "Save rule" }));

  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  const request = fetch.mock.calls.find(([url, options]) => url === endpoint && options?.method === "POST");
  expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
    questions: [question],
    threshold_comparison: "gt",
    value: "25",
    unit: "dollars",
    source: { document_id: "policy", chunk_id: 2 },
  });
  expect(screen.getByLabelText("Threshold comparison")).toHaveValue("gt");
});
