import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/i18n/messages/en.json";
import AgentVersions, { type AgentVersionState } from "./AgentVersions";

jest.mock("@/lib/navigation/hooks", () => ({ useAppPosition: () => ({}) }));

afterEach(() => jest.restoreAllMocks());

test("only the verification affordance offers an exact-version review", async () => {
  const version = {
    version: 3,
    configuration: {
      name: "Research",
      system_prompt: "Use citations.",
      task_prompt: "",
      replace_base_system_prompt: false,
      datetime_aware: false,
      document_set_ids: [],
      search_start_date: null,
      model_configuration_id: 1,
    },
    published_at: "2026-11-01T12:00:00Z",
    is_active: true,
    withdrawn_at: null,
  };
  const state: AgentVersionState = {
    can_verify: false,
    can_publish: true,
    active_version: 3,
    next_version: 4,
    company_listed: true,
    draft: null,
    versions: [version],
    tests: [],
    enrollment_blocked: false,
    audience: "Organization",
    audience_revision: null,
    shared_with: [],
  };
  const refresh = jest.fn(async () => state);
  const fetch = jest.spyOn(global, "fetch").mockResolvedValue({ ok: true } as Response);
  jest.spyOn(window, "confirm").mockReturnValue(true);
  const view = (current: AgentVersionState) => (
    <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
      <AgentVersions
        agentId={7}
        state={current}
        refresh={refresh}
        libraryNames={new Map()}
        hasUnsavedChanges={false}
      />
    </NextIntlClientProvider>
  );

  const { container, rerender } = render(view(state));
  container.querySelectorAll("details").forEach((details) => {
    details.open = true;
  });
  expect(screen.queryByRole("button", { name: "Verify version" })).toBeNull();
  rerender(view({ ...state, can_verify: true }));
  fireEvent.click(screen.getByRole("button", { name: "Verify version" }));
  await waitFor(() => expect(refresh).toHaveBeenCalled());
  expect(fetch).toHaveBeenCalledWith(
    "/api/admin/persona/7/versions/verification",
    expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ version: 3, verified: true }),
    }),
  );
});

test("reviewing a restore explains which chats are affected before it sends the request", async () => {
  const configuration = {
    name: "Research",
    system_prompt: "Use citations.",
    task_prompt: "",
    replace_base_system_prompt: false,
    datetime_aware: false,
    document_set_ids: [],
    search_start_date: null,
    model_configuration_id: 1,
  };
  const state: AgentVersionState = {
    can_publish: true,
    active_version: 2,
    next_version: 3,
    draft: null,
    versions: [2, 1].map((version) => ({
      version,
      configuration,
      published_at: "2026-11-01T12:00:00Z",
      is_active: version === 2,
      withdrawn_at: null,
    })),
    tests: [],
    enrollment_blocked: false,
    audience: "Private",
    audience_revision: null,
    shared_with: [],
  };
  const refresh = jest.fn(async () => state);
  const fetch = jest.spyOn(global, "fetch").mockResolvedValue({ ok: true } as Response);
  const { container } = render(
    <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
      <AgentVersions
        agentId={7}
        state={state}
        refresh={refresh}
        libraryNames={new Map()}
        hasUnsavedChanges={false}
      />
    </NextIntlClientProvider>,
  );
  container.querySelectorAll("details").forEach((details) => {
    details.open = true;
  });
  fireEvent.click(screen.getByRole("button", { name: "Restore version" }));
  const review = screen.getByRole("dialog", { name: "Restore version 1" });
  expect(screen.getByText("New chats will use version 1.")).toBeInTheDocument();
  expect(screen.getByText(/Chats on version 2 keep their history/)).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(within(review).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Restore version" }));
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Restore version" }),
  );
  await waitFor(() => expect(refresh).toHaveBeenCalled());
  expect(fetch).toHaveBeenCalledWith(
    "/api/persona/7/versions/rollback",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ version: 1, expected_active_version: 2 }),
    }),
  );
});
