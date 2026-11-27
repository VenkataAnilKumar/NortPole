import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/i18n/messages/en.json";
import PacksPage from "./PacksPage";

const mockGo = jest.fn();
const mockUsePermissionAuthority = jest.fn();

jest.mock("@opal/navigation", () => ({
  ...jest.requireActual("@opal/navigation"),
  useNavigation: () => ({ go: mockGo }),
}));

jest.mock("@/lib/permissions/hooks", () => ({
  usePermissionAuthority: () => mockUsePermissionAuthority(),
}));

jest.mock("swr", () => () => ({
  data: [
    {
      pack_id: "everyday-brief",
      version: "1.1.0",
      group: "everyday",
      name: "Evidence Brief",
      templates: [],
      chat_agents: [{ id: "evidence-research", name: "Evidence Research" }],
      ready_on_current_route: true,
    },
  ],
}));

afterEach(() => jest.restoreAllMocks());

test("prepares the exact pack agent draft for a user who can add agents", async () => {
  mockUsePermissionAuthority.mockReturnValue({ isGlobalHolder: false });
  const fetchDraft = jest.spyOn(global, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({ agent_id: 17 }),
  } as Response);
  const page = () => (
    <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
      <PacksPage />
    </NextIntlClientProvider>
  );
  const { rerender } = render(page());
  const button = { name: "Prepare Chat agent draft" };
  expect(screen.queryByRole("button", button)).toBeNull();

  mockUsePermissionAuthority.mockReturnValue({ isGlobalHolder: true });
  rerender(page());
  fireEvent.click(screen.getByRole("button", button));
  expect(fetchDraft).toHaveBeenCalledWith(
    "/api/packs/everyday-brief/1.1.0/chat-agents/evidence-research/draft",
    { method: "POST" }
  );
  await waitFor(() => expect(mockGo).toHaveBeenCalledWith("/app/agents/edit/17"));
});
